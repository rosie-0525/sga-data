# Hosting the viewer with a live review loop

Two processes on one EC2 box: `scripts/review_server.py` serves the working tree
and applies verdicts to it, and Caddy terminates TLS in front of it.

```
internet ──▶ :443 Caddy ──▶ 127.0.0.1:8000 review_server.py ──▶ sgaN/data/**/chapters/*.json
```

Anyone may read the books, the proposed changes, and the verdicts recorded so
far. Only a logged-in admin sees Accept / Edit / Reject, and each verdict is
written into the chapter JSON as it is made — see the "Proposed changes" section
of the top-level README for the offline half of the same loop.

## First run

```sh
# 1. the admin password (stored hashed in ~/.config/sga-review/config.json, mode 600)
python3 scripts/review_server.py --set-password

# 2. try it locally before exposing anything
python3 scripts/review_server.py --host 127.0.0.1 --port 8000
#    from your laptop:  ssh -L 8000:localhost:8000 ubuntu@<box>
#    then open          http://localhost:8000/sga7/paper.html
```

## Going public

Do these in order — Caddy validates its certificate over port 80 against live
DNS, so it must be started last.

1. **Elastic IP.** Allocate one and associate it with the instance. Without it
   the public IP changes on the next stop/start and the DNS record goes stale.
2. **Security group.** Allow inbound `80` and `443` from `0.0.0.0/0`. Leave 8000
   closed; only Caddy reaches it.
3. **DNS.** Replace the four GitHub Pages A records for `dev.grothendiecksga.com`
   with one A record pointing at the Elastic IP. Also clear the custom domain in
   the repo's GitHub Pages settings — otherwise GitHub keeps asserting the
   hostname and certificate issuance can fail. The repo's `CNAME` file is then
   vestigial.
4. **Install Caddy and the unit.**
   ```sh
   sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
   curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key \
     | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
   curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt \
     | sudo tee /etc/apt/sources.list.d/caddy-stable.list
   sudo apt update && sudo apt install -y caddy

   sudo cp deploy/sga-review.service /etc/systemd/system/
   sudo systemctl daemon-reload && sudo systemctl enable --now sga-review

   sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
   sudo systemctl reload caddy
   ```
5. **Check.** `https://dev.grothendiecksga.com/sga7/paper.html` loads with a valid
   certificate, and `/nohup.out`, `/.git/config` and `/scripts/review_server.py`
   all return 404.

## What the server writes

| Path | What it is |
| --- | --- |
| `sgaN/data/<lang>/chapters/*.json` | the corpus — an accepted proposal lands here |
| `sgaN/data/decisions.json` | verdicts so far, in the viewer's export schema (gitignored) |
| `~/.local/state/sga-review/audit.jsonl` | append-only record of every write, with full before/after |
| `~/.config/sga-review/config.json` | password hash + session secret, mode 600, outside the repo |

Nothing is committed. `git diff` is where the accumulated edits show up, and
`git status` will list the touched chapter files — commit and push them when you
want the GitHub copy to catch up.

## Recovering from a bad verdict

The panel's **Undo** restores the block, but only while it still holds exactly
what was written (an intervening edit makes it refuse rather than clobber). Past
that point, the audit log has the original text:

```sh
python3 - <<'PY'
import json, pathlib
for line in pathlib.Path.home().joinpath(".local/state/sga-review/audit.jsonl").read_text().splitlines():
    e = json.loads(line)
    print(e["at"], e["action"], e["id"], e["file"])
PY
```

Each record carries `before` and `after` in full, so a block can be put back by
hand. `git checkout -- <file>` also works when the file has not been committed
since the edit.
