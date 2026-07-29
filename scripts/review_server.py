#!/usr/bin/env python3
"""Serve the corpus and apply review verdicts to it in place.

The hosted half of the proposed-changes loop. Offline, a reviewer exports
decisions.json from the viewer and runs apply_proposals.py; here the viewer
POSTs each verdict and the write lands in the chapter JSON immediately, so the
next reader to load the page sees the corrected text.

  anyone      reads the books and the proposals, and the verdicts so far
  the admin   logs in with a shared password and decides

Every write goes through proposals_lib.apply_decision — the same guards the CLI
applies (address resolves, `before` still matches, single root element, fr/en
block alignment holds). A verdict that trips one is refused with a message, not
forced. Verdicts are recorded per book in <book>/data/decisions.json (the same
schema the viewer exports, so apply_proposals.py can still read it) and every
write is appended to an audit log outside the repo.

Usage:
  review_server.py --set-password              # once, to create the config
  review_server.py --host 127.0.0.1 --port 8000

Nothing here commits: `git diff` is where the accumulated edits show up.
"""
import argparse
import hashlib
import hmac
import http.cookies
import json
import os
import secrets
import sys
import threading
import time
from datetime import datetime, timezone
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from proposals_lib import (  # noqa: E402
    BOOKS, ROOT, VERDICTS, apply_decision, load_json, proposals_path,
)

CONFIG_PATH = Path.home() / ".config" / "sga-review" / "config.json"
AUDIT_PATH = Path.home() / ".local" / "state" / "sga-review" / "audit.jsonl"

COOKIE_NAME = "sga_admin"
SESSION_MAX_AGE = 30 * 24 * 3600          # 30 days
MAX_BODY = 2 * 1024 * 1024                # a block's html, with room to spare
LOGIN_MAX_FAILURES = 10                   # per IP …
LOGIN_WINDOW = 15 * 60                    # … per quarter hour

# scrypt cost. n=2**14 keeps a login around 100 ms on a t2.medium, which is
# plenty against a password file that never leaves the box.
SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32}

# Never served, whatever the URL says: the git dir, editor state, this script
# and its siblings, and the 100 MB+ nohup.out sitting in the repo root.
DENY_SEGMENTS = {"scripts", "node_modules", "__pycache__"}
DENY_NAMES = {"nohup.out"}

# One lock for every read-modify-write of a chapter file or a decisions file.
# Verdicts are rare and the critical section is a few milliseconds, so a single
# global lock costs nothing and removes any chance of two admins interleaving.
LOCK = threading.RLock()

_runs = {}          # book -> (mtime, run dict)
_failures = {}      # ip -> [timestamps]


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ----------------------------------------------------------------- config ----

def load_config(path=CONFIG_PATH):
    if not Path(path).exists():
        raise SystemExit(
            f"no admin config at {path} — run: {sys.argv[0]} --set-password")
    cfg = load_json(path)
    for key in ("salt", "password_hash", "session_secret"):
        if not cfg.get(key):
            raise SystemExit(f"{path}: missing {key!r}")
    return cfg


def set_password(path=CONFIG_PATH):
    """Create (or replace) the admin config. Kept outside the repo so it can
    never be served by the static handler or committed by accident."""
    import getpass
    pw = getpass.getpass("New admin password: ")
    if len(pw) < 8:
        raise SystemExit("password must be at least 8 characters")
    if pw != getpass.getpass("Repeat: "):
        raise SystemExit("passwords did not match")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    salt = secrets.token_bytes(16)
    cfg = {
        "salt": salt.hex(),
        "password_hash": hashlib.scrypt(pw.encode(), salt=salt, **SCRYPT).hex(),
        # Rotating this invalidates every outstanding session cookie.
        "session_secret": secrets.token_hex(32),
        "updatedAt": now_iso(),
    }
    path.write_text(json.dumps(cfg, indent=1) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    print(f"wrote {path} (mode 600)")


def password_ok(cfg, password):
    want = bytes.fromhex(cfg["password_hash"])
    got = hashlib.scrypt(password.encode(), salt=bytes.fromhex(cfg["salt"]), **SCRYPT)
    return hmac.compare_digest(want, got)


# ---------------------------------------------------------------- sessions ----

def make_token(cfg, issued=None):
    issued = str(int(issued if issued is not None else time.time()))
    sig = hmac.new(cfg["session_secret"].encode(), issued.encode(),
                   hashlib.sha256).hexdigest()
    return f"{issued}.{sig}"


def token_ok(cfg, token):
    if not token or "." not in token:
        return False
    issued, _, sig = token.partition(".")
    if not issued.isdigit():
        return False
    expected = hmac.new(cfg["session_secret"].encode(), issued.encode(),
                        hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return False
    return time.time() - int(issued) < SESSION_MAX_AGE


def rate_limited(ip):
    hits = [t for t in _failures.get(ip, []) if time.time() - t < LOGIN_WINDOW]
    _failures[ip] = hits
    return len(hits) >= LOGIN_MAX_FAILURES


def record_failure(ip):
    _failures.setdefault(ip, []).append(time.time())


# ------------------------------------------------------------------- runs ----

def load_run(book):
    """The book's proposals.json, re-read whenever it changes on disk (a new
    run can be published under a live server)."""
    path = proposals_path(book)
    if not path.exists():
        return None
    mtime = path.stat().st_mtime
    cached = _runs.get(book)
    if not cached or cached[0] != mtime:
        _runs[book] = (mtime, load_json(path))
    return _runs[book][1]


def decisions_path(book):
    return ROOT / book / "data" / "decisions.json"


def load_decisions(book):
    path = decisions_path(book)
    if not path.exists():
        return {}
    try:
        doc = load_json(path)
    except (ValueError, OSError):
        return {}
    out = {}
    for d in doc.get("decisions") or []:
        if isinstance(d, dict) and d.get("id"):
            out[d["id"]] = d
    return out


def progress_all():
    """{book: {total, decided}} for every book with a run published.

    What the landing page draws its bars from. `decided` counts the proposals of
    the *current* run that carry a verdict, so a decisions file left over from an
    earlier run contributes nothing rather than overcounting. Staleness is not
    computed: it would mean reading every chapter of every book to answer one
    page load.
    """
    out = {}
    for book in BOOKS:
        run = load_run(book)
        if run is None:
            continue
        ids = {p.get("id") for p in (run.get("proposals") or []) if p.get("id")}
        decided = load_decisions(book)
        out[book] = {
            "total": len(ids),
            "decided": sum(1 for pid, d in decided.items()
                           if pid in ids and d.get("verdict") in VERDICTS),
        }
    return out


def save_decisions(book, by_id):
    """Written in the viewer's own export schema, so this file doubles as a
    decisions.json that apply_proposals.py --decisions can replay offline."""
    run = load_run(book) or {}
    doc = {
        "schemaVersion": 1,
        "book": book,
        "proposalsGeneratedAt": run.get("generatedAt"),
        "decidedAt": now_iso(),
        "decisions": [by_id[k] for k in sorted(by_id)],
    }
    path = decisions_path(book)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    tmp.replace(path)          # atomic: a reader never sees a half-written file


def audit(path, entry):
    """Append-only record of every write. This is the only history we keep —
    the server does not commit — so it carries the full before/after html."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- handler ----

class ReviewHandler(SimpleHTTPRequestHandler):
    server_version = "sga-review"

    def __init__(self, *args, config=None, audit_path=AUDIT_PATH, **kwargs):
        self.config = config
        self.audit_path = audit_path
        super().__init__(*args, directory=str(ROOT), **kwargs)

    # -- plumbing --------------------------------------------------------

    def client_ip(self):
        fwd = self.headers.get("X-Forwarded-For", "")
        return fwd.split(",")[0].strip() or self.client_address[0]

    def is_https(self):
        # Caddy sets this on every proxied request; direct hits to :8000 are
        # local-only, so trusting it here is safe.
        return self.headers.get("X-Forwarded-Proto", "").lower() == "https"

    def send_json(self, obj, status=HTTPStatus.OK, cookie=None):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(body)

    def fail(self, status, message):
        self.send_json({"ok": False, "error": message}, status=status)

    def read_json(self):
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return None, "expected Content-Type: application/json"
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None, "bad Content-Length"
        if length <= 0:
            return None, "empty body"
        if length > MAX_BODY:
            return None, "body too large"
        try:
            return json.loads(self.rfile.read(length).decode("utf-8")), None
        except (ValueError, UnicodeDecodeError) as exc:
            return None, f"invalid JSON: {exc}"

    def is_admin(self):
        raw = self.headers.get("Cookie")
        if not raw:
            return False
        try:
            jar = http.cookies.SimpleCookie(raw)
        except http.cookies.CookieError:
            return False
        morsel = jar.get(COOKIE_NAME)
        return bool(morsel) and token_ok(self.config, morsel.value)

    def session_cookie(self, value, max_age=SESSION_MAX_AGE):
        # SameSite=Strict is what makes the mutating endpoints CSRF-safe: a
        # cross-site form post simply arrives without the cookie.
        bits = [f"{COOKIE_NAME}={value}", "Path=/", "HttpOnly", "SameSite=Strict",
                f"Max-Age={max_age}"]
        if self.is_https():
            bits.append("Secure")
        return "; ".join(bits)

    # -- static half -----------------------------------------------------

    def denied(self):
        parts = self.path.split("?")[0].split("#")[0].split("/")
        for seg in parts:
            if seg.startswith(".") and seg not in ("", ".", ".."):
                return True
            if seg in DENY_SEGMENTS or seg in DENY_NAMES:
                return True
        return False

    def end_headers(self):
        # The corpus is edited under a live server, so a reader must never be
        # handed a cached chapter. no-cache still allows revalidation, which
        # keeps the big vendored MathJax payloads cheap (they are not in data/).
        path = self.path.split("?")[0]
        if "/data/" in path and path.endswith(".json"):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self):
        route = self.path.split("?")[0]
        if route == "/api/session":
            return self.send_json({"ok": True, "admin": self.is_admin()})
        if route == "/api/progress":
            with LOCK:
                books = progress_all()
            return self.send_json({"ok": True, "books": books})
        if route.startswith("/api/"):
            return self.fail(HTTPStatus.NOT_FOUND, "no such endpoint")
        if self.denied():
            return self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
        return super().do_GET()

    def do_HEAD(self):
        if self.path.startswith("/api/") or self.denied():
            return self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
        return super().do_HEAD()

    # -- api -------------------------------------------------------------

    def do_POST(self):
        route = self.path.split("?")[0]
        handlers = {
            "/api/login": self.api_login,
            "/api/logout": self.api_logout,
            "/api/decide": self.api_decide,
            "/api/undo": self.api_undo,
        }
        fn = handlers.get(route)
        if not fn:
            return self.fail(HTTPStatus.NOT_FOUND, "no such endpoint")
        body, err = self.read_json()
        if err and route != "/api/logout":
            return self.fail(HTTPStatus.BAD_REQUEST, err)
        return fn(body or {})

    def api_login(self, body):
        ip = self.client_ip()
        if rate_limited(ip):
            return self.fail(HTTPStatus.TOO_MANY_REQUESTS,
                             "too many attempts — wait 15 minutes")
        password = body.get("password")
        if not isinstance(password, str) or not password_ok(self.config, password):
            record_failure(ip)
            time.sleep(0.5)
            return self.fail(HTTPStatus.UNAUTHORIZED, "wrong password")
        _failures.pop(ip, None)
        self.send_json({"ok": True, "admin": True},
                       cookie=self.session_cookie(make_token(self.config)))

    def api_logout(self, body):
        self.send_json({"ok": True, "admin": False},
                       cookie=self.session_cookie("", max_age=0))

    def require_admin(self):
        if self.is_admin():
            return True
        self.fail(HTTPStatus.UNAUTHORIZED, "not logged in")
        return False

    def lookup(self, body):
        """(book, proposal, error) for a request naming a book and a proposal."""
        book = body.get("book")
        pid = body.get("id")
        if book not in BOOKS:
            return None, None, f"unknown book {book!r}"
        run = load_run(book)
        if run is None:
            return None, None, f"no proposals run published for {book}"
        for p in run.get("proposals") or []:
            if p.get("id") == pid:
                return book, p, None
        return None, None, f"proposal {pid!r} is not in the current {book} run"

    def api_decide(self, body):
        if not self.require_admin():
            return
        verdict = body.get("verdict")
        if verdict not in VERDICTS:
            return self.fail(HTTPStatus.BAD_REQUEST, f"unknown verdict {verdict!r}")
        with LOCK:
            book, p, err = self.lookup(body)
            if err:
                return self.fail(HTTPStatus.NOT_FOUND, err)

            new_html = None
            if verdict != "reject":
                new_html = body.get("html") if verdict == "edit" else p.get("after")
                if not isinstance(new_html, str) or not new_html.strip():
                    return self.fail(HTTPStatus.BAD_REQUEST,
                                     "edit verdict with no replacement html")
                ok, err, path = apply_decision(book, p, new_html)
                if not ok:
                    # Conflict / multi-root / alignment: the data moved on, or
                    # the replacement would lose content. Never forced.
                    return self.fail(HTTPStatus.CONFLICT, err)
                audit(self.audit_path, {
                    "at": now_iso(), "ip": self.client_ip(), "action": "apply",
                    "book": book, "id": p.get("id"), "verdict": verdict,
                    "lang": p.get("lang"), "chapterId": p.get("chapterId"),
                    "pageId": p.get("pageId"), "target": p.get("target", "block"),
                    "index": p.get("footnoteIndex") if p.get("target") == "footnote"
                             else p.get("blockIndex"),
                    "file": str(path.relative_to(ROOT)),
                    "before": p.get("before"), "after": new_html,
                })

            rec = {"id": p["id"], "verdict": verdict, "at": now_iso()}
            if verdict == "edit":
                rec["html"] = new_html
            if isinstance(body.get("note"), str) and body["note"].strip():
                rec["note"] = body["note"].strip()
            by_id = load_decisions(book)
            by_id[p["id"]] = rec
            save_decisions(book, by_id)

        self.send_json({"ok": True, "id": p["id"], "verdict": verdict,
                        "html": new_html})

    def api_undo(self, body):
        """Put a block back the way it was. With no git history behind us this
        is the only way back from a wrong Accept, so it is guarded the same way
        the apply was: the block must still hold exactly what we wrote."""
        if not self.require_admin():
            return
        with LOCK:
            book, p, err = self.lookup(body)
            if err:
                return self.fail(HTTPStatus.NOT_FOUND, err)
            by_id = load_decisions(book)
            rec = by_id.get(p["id"])
            if not rec:
                return self.fail(HTTPStatus.NOT_FOUND, "no verdict recorded")

            if rec["verdict"] != "reject":
                applied = rec.get("html") if rec["verdict"] == "edit" else p.get("after")
                # Invert the proposal: what we wrote becomes `before`, and the
                # original `before` becomes the replacement.
                inverse = dict(p, before=applied)
                ok, err, path = apply_decision(book, inverse, p.get("before"))
                if not ok:
                    return self.fail(HTTPStatus.CONFLICT, err)
                audit(self.audit_path, {
                    "at": now_iso(), "ip": self.client_ip(), "action": "undo",
                    "book": book, "id": p.get("id"), "verdict": rec["verdict"],
                    "lang": p.get("lang"), "chapterId": p.get("chapterId"),
                    "pageId": p.get("pageId"),
                    "file": str(path.relative_to(ROOT)),
                    "before": applied, "after": p.get("before"),
                })

            del by_id[p["id"]]
            save_decisions(book, by_id)

        self.send_json({"ok": True, "id": p["id"], "html": p.get("before")})

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.client_ip(), fmt % args))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1",
                    help="bind address (default 127.0.0.1; Caddy fronts it)")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--config", default=str(CONFIG_PATH))
    ap.add_argument("--audit", default=str(AUDIT_PATH))
    ap.add_argument("--set-password", action="store_true",
                    help="create/replace the admin config, then exit")
    args = ap.parse_args()

    if args.set_password:
        set_password(args.config)
        return

    cfg = load_config(args.config)
    handler = partial(ReviewHandler, config=cfg, audit_path=Path(args.audit))
    httpd = ThreadingHTTPServer((args.host, args.port), handler)
    httpd.daemon_threads = True
    print(f"serving {ROOT} on http://{args.host}:{args.port}", file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
