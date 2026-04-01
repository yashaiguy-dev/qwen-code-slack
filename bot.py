#!/usr/bin/env python3
"""
Qwen Code Slack Bot — runs Qwen Code headless via Slack Socket Mode.

No server. No Cloudflare. No API key. Just Qwen OAuth (free credits) + Slack tokens.
Each Slack thread = its own Qwen Code session (just like Claude homebase).

Setup:
  1. Install Qwen Code:  npm install -g @qwen-code/qwen-code@latest
  2. Login once:          qwen  (complete OAuth in browser — free credits)
  3. Create Slack app with Socket Mode (see README.md)
  4. Copy .env.example → .env, fill in Slack tokens
  5. pip3 install -r requirements.txt
  6. python3 bot.py
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_DIR = Path(__file__).parent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("qwen-bot")

_rotating_handler = logging.handlers.RotatingFileHandler(
    LOG_DIR / "bot.log",
    maxBytes=5 * 1024 * 1024,
    backupCount=3,
    encoding="utf-8",
)
_rotating_handler.setFormatter(
    logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
)
logger.addHandler(_rotating_handler)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
AUTHORIZED_USERS = set(
    u.strip() for u in os.environ.get("AUTHORIZED_USERS", "").split(",") if u.strip()
)
QWEN_WORK_DIR = os.path.expanduser(os.environ.get("QWEN_WORK_DIR", "~/qwen-workspace"))
QWEN_TIMEOUT = int(os.environ.get("QWEN_TIMEOUT", "300"))  # 5 min default
MAX_SLACK_MSG_LEN = 3900

# Ensure workspace exists
Path(QWEN_WORK_DIR).mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Slack app (Socket Mode — no public URL needed)
# ---------------------------------------------------------------------------

app = App(token=SLACK_BOT_TOKEN)
slack_client = WebClient(token=SLACK_BOT_TOKEN)

# Cache for Slack user display names
_user_name_cache: dict[str, str] = {}


def _get_user_name(user_id: str) -> str:
    if user_id in _user_name_cache:
        return _user_name_cache[user_id]
    try:
        info = slack_client.users_info(user=user_id)
        profile = info["user"].get("profile", {})
        name = (
            profile.get("display_name")
            or profile.get("real_name")
            or info["user"].get("real_name")
            or user_id
        )
        _user_name_cache[user_id] = name
    except Exception:
        name = user_id
        _user_name_cache[user_id] = name
    return name


# ---------------------------------------------------------------------------
# Session store: thread_ts → Qwen session_id (file-backed)
# Each Slack thread gets its own Qwen Code session — just like Claude homebase
# ---------------------------------------------------------------------------

SESSION_FILE = LOG_DIR / ".sessions.json"
MAX_SESSIONS = 200


def _load_sessions() -> dict:
    try:
        return json.loads(SESSION_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_session(thread_ts: str, session_id: str) -> None:
    sessions = _load_sessions()
    sessions[thread_ts] = session_id
    if len(sessions) > MAX_SESSIONS:
        for key in sorted(sessions.keys())[:-MAX_SESSIONS]:
            del sessions[key]
    SESSION_FILE.write_text(json.dumps(sessions))


def _get_session(thread_ts: str) -> str | None:
    return _load_sessions().get(thread_ts)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def is_authorized(user_id: str) -> bool:
    return not AUTHORIZED_USERS or user_id in AUTHORIZED_USERS


# ---------------------------------------------------------------------------
# Qwen Code CLI — streaming headless mode
# ---------------------------------------------------------------------------


def call_qwen_streaming(
    prompt: str,
    session_id: str | None,
    on_text: callable,
) -> str | None:
    """Invoke `qwen -p` with streaming JSON output.

    Each assistant text block calls on_text() as it arrives.
    Returns the session_id from the result message (for thread continuity).
    """
    cmd = [
        "qwen",
        "-p", prompt,
        "--output-format", "stream-json",
        "--yolo",  # Auto-approve all actions (file edits, shell commands, etc.)
    ]
    if session_id:
        cmd.extend(["--resume", session_id])

    logger.info(f"Spawning qwen CLI (resume={session_id or 'none'})")

    stderr_tmp = tempfile.NamedTemporaryFile(mode="w+", suffix=".stderr", delete=False)

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=stderr_tmp,
        text=True,
        cwd=QWEN_WORK_DIR,
    )

    new_session_id = session_id
    deadline = time.time() + QWEN_TIMEOUT

    try:
        for line in proc.stdout:
            if time.time() > deadline:
                proc.kill()
                raise subprocess.TimeoutExpired(cmd, QWEN_TIMEOUT)

            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")

            if msg_type == "assistant":
                content = data.get("message", {}).get("content", [])
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text = block.get("text", "").strip()
                        if text:
                            on_text(text)

            elif msg_type == "result":
                new_session_id = data.get("session_id") or new_session_id
                # Also check for text in result
                result_text = data.get("result", "").strip()
                if result_text:
                    on_text(result_text)

        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise
    except Exception as e:
        proc.kill()
        raise RuntimeError(f"Qwen Code streaming error: {e}")
    finally:
        stderr_tmp.close()

    if proc.returncode != 0:
        try:
            stderr_text = Path(stderr_tmp.name).read_text().strip()
        except Exception:
            stderr_text = "(stderr unavailable)"
        logger.error(f"Qwen CLI failed (rc={proc.returncode}): {stderr_text[:500]}")
        try:
            os.unlink(stderr_tmp.name)
        except OSError:
            pass
        raise RuntimeError(f"Qwen Code error: {stderr_text[:300]}")

    try:
        os.unlink(stderr_tmp.name)
    except OSError:
        pass

    return new_session_id


# ---------------------------------------------------------------------------
# Markdown → Slack mrkdwn
# ---------------------------------------------------------------------------


def md_to_slack(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    text = re.sub(r"~~(.+?)~~", r"~\1~", text)
    text = re.sub(r"```\w*\n", "```\n", text)
    text = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)
    return text


def chunk_message(text: str) -> list[str]:
    if len(text) <= MAX_SLACK_MSG_LEN:
        return [text]

    chunks = []
    while text:
        if len(text) <= MAX_SLACK_MSG_LEN:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, MAX_SLACK_MSG_LEN)
        if split_at == -1:
            split_at = text.rfind(" ", 0, MAX_SLACK_MSG_LEN)
        if split_at == -1:
            split_at = MAX_SLACK_MSG_LEN
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


# ---------------------------------------------------------------------------
# Message processing (background thread)
# ---------------------------------------------------------------------------


def process_message_async(event: dict) -> None:
    user_id = event.get("user", "")
    text = event.get("text", "").strip()
    channel = event.get("channel", "")
    thread_ts = event.get("thread_ts") or event.get("ts")
    msg_ts = event.get("ts")

    # Strip bot mention
    text = re.sub(r"<@[A-Z0-9]+>\s*", "", text).strip()
    if not text:
        return

    # Prepend sender name
    sender_name = _get_user_name(user_id)
    text = f"[{sender_name}] says:\n{text}"

    # Add eyes reaction as thinking indicator
    try:
        slack_client.reactions_add(channel=channel, name="eyes", timestamp=msg_ts)
    except Exception:
        pass

    # Get existing session for this thread (or None for new thread)
    session_id = _get_session(thread_ts)
    all_texts = []

    def on_text(text_block: str):
        all_texts.append(text_block)
        slack_text = md_to_slack(text_block)
        for chunk in chunk_message(slack_text):
            slack_client.chat_postMessage(
                channel=channel, text=chunk, thread_ts=thread_ts,
            )

    start = time.time()
    try:
        new_session_id = call_qwen_streaming(text, session_id, on_text)
    except subprocess.TimeoutExpired:
        _remove_reaction(channel, msg_ts)
        minutes = QWEN_TIMEOUT // 60
        slack_client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            text=f"Timed out after {minutes} minutes. Try a simpler question?",
        )
        return
    except FileNotFoundError:
        _remove_reaction(channel, msg_ts)
        slack_client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            text="`qwen` not found. Install: `npm install -g @qwen-code/qwen-code@latest` then run `qwen` once to login.",
        )
        return
    except RuntimeError as e:
        _remove_reaction(channel, msg_ts)
        slack_client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            text=f"Error: {e}",
        )
        return
    duration = time.time() - start

    # Save session for thread continuity
    if new_session_id and thread_ts:
        _save_session(thread_ts, new_session_id)

    _remove_reaction(channel, msg_ts)

    full_response = "\n\n".join(all_texts)
    logger.info(f"Responded to {user_id} in {duration:.1f}s ({len(full_response)} chars, session={new_session_id})")


def _remove_reaction(channel: str, ts: str) -> None:
    try:
        slack_client.reactions_remove(channel=channel, name="eyes", timestamp=ts)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Slack event handlers
# ---------------------------------------------------------------------------


@app.event("app_mention")
def handle_mention(event, say):
    """Handle @QwenCode mentions in channels."""
    user_id = event.get("user", "")
    if not is_authorized(user_id):
        say(text="I only respond to authorized users.", thread_ts=event.get("ts"))
        return
    threading.Thread(target=process_message_async, args=(event,), daemon=True).start()


@app.event("message")
def handle_dm(event, say):
    """Handle direct messages."""
    subtype = event.get("subtype")
    if subtype:
        return

    # Only respond in DMs
    if event.get("channel_type") != "im":
        return

    user_id = event.get("user", "")
    if not is_authorized(user_id):
        say(text="I only respond to authorized users.", thread_ts=event.get("ts"))
        return

    threading.Thread(target=process_message_async, args=(event,), daemon=True).start()


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))

    print("=" * 50)
    print("  Qwen Code Slack Bot")
    print("=" * 50)
    print(f"  Workspace:  {QWEN_WORK_DIR}")
    print(f"  Mode:       Socket Mode (no public URL)")
    print(f"  Timeout:    {QWEN_TIMEOUT}s")
    print(f"  Auth:       {AUTHORIZED_USERS or 'all users'}")
    print("=" * 50)
    print("  Bot is running! Send a message in Slack.")
    print()

    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()
