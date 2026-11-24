#!/usr/bin/env python3
"""Send a trader message to WhatsApp (CallMeBot) and Telegram. Standard library only.

    python3 notify.py status                                  # which channels are set up
    python3 notify.py send "TSLA hit its stop at 358.32"      # every channel that is set up
    python3 notify.py send --file trader/brief.txt --title "Pre-market brief"
    echo "text" | python3 notify.py send -                    # from stdin
    python3 notify.py send "..." --channels whatsapp          # one channel only
    python3 notify.py send "..." --key orb-2026-11-24-TSLA    # send once per key, ever
    python3 notify.py send "..." --dry-run                    # print, send nothing

Channels and their environment variables (set them in the cloud environment's
settings or your shell, never in a file in the repo and never in the chat):

  whatsapp  CALLMEBOT_PHONE   your number with the country code, e.g. +33612345678
            CALLMEBOT_APIKEY  the key CallMeBot sent you on WhatsApp
            https://api.callmebot.com/whatsapp.php?phone=..&text=..&apikey=..
  telegram  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (the same pair tradepilot reads)
            https://api.telegram.org/bot<token>/sendMessage

Exit codes: 0 delivered on at least one channel (or --dry-run, or a --key
already sent), 1 every channel failed, 2 bad usage, 3 no channel set up.
Errors never print a key, a token or a phone number.
"""

import argparse
import datetime as _dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

CALLMEBOT = "https://api.callmebot.com/whatsapp.php"
TELEGRAM = "https://api.telegram.org/bot%s/sendMessage"
LIMITS = {"whatsapp": 1500, "telegram": 4000}
CHANNELS = ("whatsapp", "telegram")
KEEP_DAYS = 30
UA = "day-trader-skill-notify/1.0"


class NotifyError(Exception):
    pass


def configured(env=None):
    """{channel: True/False}, from the environment only."""
    env = os.environ if env is None else env
    return {
        "whatsapp": bool(env.get("CALLMEBOT_PHONE") and env.get("CALLMEBOT_APIKEY")),
        "telegram": bool(env.get("TELEGRAM_BOT_TOKEN") and env.get("TELEGRAM_CHAT_ID")),
    }


def chunks(text, limit):
    """Split on line breaks so each part fits; a single long line is cut hard."""
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []
    parts, cur = [], ""
    for line in text.split("\n"):
        while len(line) > limit:
            if cur:
                parts.append(cur)
                cur = ""
            parts.append(line[:limit])
            line = line[limit:]
        candidate = line if not cur else cur + "\n" + line
        if len(candidate) > limit:
            parts.append(cur)
            cur = line
        else:
            cur = candidate
    if cur:
        parts.append(cur)
    if len(parts) > 1:
        parts = ["(%d/%d) %s" % (i + 1, len(parts), p) for i, p in enumerate(parts)]
    return parts


def _http(req, timeout=20):
    """The one place that touches the network (tests replace it)."""
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read(2000).decode("utf-8", "replace")


def send_whatsapp(text, env, http=_http):
    url = CALLMEBOT + "?" + urllib.parse.urlencode({
        "phone": env["CALLMEBOT_PHONE"], "text": text, "apikey": env["CALLMEBOT_APIKEY"]})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        status, body = http(req)
    except urllib.error.HTTPError as exc:
        raise NotifyError("WhatsApp: HTTP %s" % exc.code)
    except (urllib.error.URLError, OSError) as exc:
        raise NotifyError("WhatsApp: could not reach CallMeBot (%s)" % type(exc).__name__)
    low = body.lower()
    if status != 200 or "apikey is invalid" in low or "error" in low and "queued" not in low:
        raise NotifyError("WhatsApp: CallMeBot refused the message (HTTP %s)" % status)
    return True


def send_telegram(text, env, http=_http):
    data = json.dumps({"chat_id": env["TELEGRAM_CHAT_ID"], "text": text,
                       "disable_web_page_preview": True}).encode("utf-8")
    req = urllib.request.Request(TELEGRAM % env["TELEGRAM_BOT_TOKEN"], data=data,
                                 headers={"Content-Type": "application/json", "User-Agent": UA})
    try:
        status, body = http(req)
    except urllib.error.HTTPError as exc:
        raise NotifyError("Telegram: HTTP %s" % exc.code)
    except (urllib.error.URLError, OSError) as exc:
        raise NotifyError("Telegram: could not reach the API (%s)" % type(exc).__name__)
    if status != 200 or '"ok":true' not in body.replace(" ", ""):
        raise NotifyError("Telegram: the API refused the message (HTTP %s)" % status)
    return True


SENDERS = {"whatsapp": send_whatsapp, "telegram": send_telegram}


def load_state(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_state(path, state, now):
    cutoff = (now - _dt.timedelta(days=KEEP_DAYS)).isoformat()
    state["sent"] = {k: v for k, v in state.get("sent", {}).items() if v >= cutoff}
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
        fh.write("\n")


def deliver(text, channels, env, http=_http, pause=1.0):
    """Send text on each channel. Returns ({channel: "sent" | error}, delivered_any)."""
    results = {}
    for ch in channels:
        parts = chunks(text, LIMITS[ch])
        try:
            for i, part in enumerate(parts):
                if i:
                    time.sleep(pause)  # CallMeBot drops bursts
                SENDERS[ch](part, env, http=http)
            results[ch] = "sent (%d part%s)" % (len(parts), "" if len(parts) == 1 else "s")
        except NotifyError as exc:
            results[ch] = str(exc)
    return results, any(v.startswith("sent") for v in results.values())


def read_text(args):
    if args.file:
        with open(args.file, encoding="utf-8") as fh:
            text = fh.read()
    elif args.text == ["-"]:
        text = sys.stdin.read()
    else:
        text = " ".join(args.text or [])
    text = text.strip()
    if args.title:
        text = "%s\n%s" % (args.title.strip(), text) if text else args.title.strip()
    return text


def main(argv=None, env=None, http=_http):
    env = os.environ if env is None else env
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status", help="which channels are set up (no secrets shown)")
    sp = sub.add_parser("send", help="send a message")
    sp.add_argument("text", nargs="*", help="the message, or - for stdin")
    sp.add_argument("--file", help="read the message from this file")
    sp.add_argument("--title", help="first line, e.g. 'Pre-market brief'")
    sp.add_argument("--channels", help="comma separated: whatsapp,telegram (default: all set up)")
    sp.add_argument("--key", help="send at most once per key (kept 30 days)")
    sp.add_argument("--state", default="trader/state/notify.json")
    sp.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    ready = configured(env)
    if args.cmd == "status":
        for ch in CHANNELS:
            print("%-9s %s" % (ch, "ready" if ready[ch] else "not set up"))
        if not any(ready.values()):
            print("No channel set up: see the variables at the top of notify.py.")
        return 0 if any(ready.values()) else 3
    if args.cmd != "send":
        ap.print_help()
        return 2

    text = read_text(args)
    if not text:
        print("notify: nothing to send", file=sys.stderr)
        return 2
    wanted = [c.strip().lower() for c in (args.channels or ",".join(CHANNELS)).split(",") if c.strip()]
    bad = [c for c in wanted if c not in CHANNELS]
    if bad:
        print("notify: unknown channel %s (choose from %s)" % (", ".join(bad), ", ".join(CHANNELS)),
              file=sys.stderr)
        return 2
    now = _dt.datetime.now(_dt.timezone.utc)
    state = load_state(args.state) if args.key else {}
    if args.key and args.key in state.get("sent", {}):
        print("already sent under key %s on %s: skipped" % (args.key, state["sent"][args.key]))
        return 0
    if args.dry_run:
        for ch in wanted:
            parts = chunks(text, LIMITS[ch])
            print("[dry run] %s, %d part(s)%s:" % (ch, len(parts), "" if ready[ch] else " (not set up)"))
            for p in parts:
                print(p)
        return 0
    channels = [c for c in wanted if ready[c]]
    if not channels:
        print("notify: no channel set up among %s. Set the environment variables listed in "
              "notify.py (python3 notify.py status)." % ", ".join(wanted), file=sys.stderr)
        return 3
    results, ok = deliver(text, channels, env, http=http)
    for ch, res in results.items():
        print("%-9s %s" % (ch, res))
    for ch in wanted:
        if not ready[ch]:
            print("%-9s not set up, skipped" % ch)
    if ok and args.key:
        state.setdefault("sent", {})[args.key] = now.isoformat()
        save_state(args.state, state, now)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
