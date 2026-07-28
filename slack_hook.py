#!/usr/bin/env python3
"""Send a Slack message using a bot token from the environment."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SLACK_API_URL = "https://slack.com/api/chat.postMessage"


class SlackHookError(RuntimeError):
    """Raised when the hook cannot deliver a message."""


def send_slack_message(
    text: str,
    *,
    token: str | None = None,
    channel: str | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Post ``text`` to Slack and return Slack's response payload."""
    token = token or os.environ.get("SLACK_BOT_TOKEN")
    channel = channel or os.environ.get("SLACK_CHANNEL_ID")

    if not token:
        raise SlackHookError("SLACK_BOT_TOKEN is not set")
    if not channel:
        raise SlackHookError("SLACK_CHANNEL_ID is not set")
    if not text.strip():
        raise SlackHookError("message text is empty")

    body = json.dumps({"channel": channel, "text": text}).encode("utf-8")
    request = Request(
        SLACK_API_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise SlackHookError(f"Slack returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise SlackHookError(f"could not reach Slack: {exc.reason}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SlackHookError("Slack returned an invalid response") from exc

    if not payload.get("ok"):
        raise SlackHookError(f"Slack rejected the message: {payload.get('error', 'unknown_error')}")

    return payload


def _message_from_command_line(arguments: list[str]) -> str:
    if arguments:
        return " ".join(arguments)
    if not sys.stdin.isatty():
        return sys.stdin.read().rstrip("\n")
    raise SlackHookError("provide a message as arguments or pipe it on standard input")


def _escape_slack_text(value: str) -> str:
    """Escape characters Slack treats as markup delimiters."""
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _message_from_codex_stop(payload: dict[str, Any]) -> str:
    """Create a compact notification from a Codex Stop-hook payload."""
    if payload.get("hook_event_name") != "Stop":
        raise SlackHookError("expected a Codex Stop hook payload")

    cwd = payload.get("cwd")
    project = Path(cwd).name if isinstance(cwd, str) and cwd else "unknown project"
    return f":white_check_mark: Codex completed a task in *{_escape_slack_text(project)}*."


def main(arguments: list[str] | None = None) -> int:
    codex_hook_mode = False
    try:
        arguments = sys.argv[1:] if arguments is None else arguments
        if arguments == ["--codex-stop"]:
            codex_hook_mode = True
            try:
                payload = json.load(sys.stdin)
            except json.JSONDecodeError as exc:
                raise SlackHookError("Codex supplied invalid hook input") from exc
            if not isinstance(payload, dict):
                raise SlackHookError("Codex hook input must be a JSON object")
            message = _message_from_codex_stop(payload)
        else:
            message = _message_from_command_line(arguments)
        result = send_slack_message(message)
    except SlackHookError as exc:
        print(f"slack-hook: {exc}", file=sys.stderr)
        return 1

    if codex_hook_mode:
        # Stop hooks must return a JSON object on stdout when they exit 0.
        print("{}")
    else:
        print(f"Slack message sent (channel={result.get('channel')}, ts={result.get('ts')})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
