---
name: trader-notify
description: >-
  Notifications. Sends what the other trader skills found to the user's phone and
  files: WhatsApp (CallMeBot), the Telegram bot shared with tradepilot, a dated
  report in the "Day Trader" folder of Google Drive, an e-mail to the user's own
  Gmail, and the Claude app's push notification. Sends a short alert, never a
  wall of text; sends each alert once (a key per event); never sends a key, a
  token, an account number or an order to place. Use when the user says "notify
  me", "send it to WhatsApp", "send me the brief", "ping me if", "put it in
  Drive", "mail me the summary", or at the end of every scheduled trader agent run
  (premarket-briefer, orb-hunter, news-sentinel, evening-reviewer).
argument-hint: "[status | send TEXT]"
---

# trader-notify

The last step of every automated run: tell the user, on the channels they chose,
what changed and what (if anything) needs their decision. It never decides for
them and never places an order: a notification can say "TSLA triggered, the
plan is ready, open /trader-broker to review it", never "bought TSLA".

`${CLAUDE_SKILL_DIR}` below is this skill's folder.

```bash
python3 "${CLAUDE_SKILL_DIR}/notify.py" status                       # which channels are ready
python3 "${CLAUDE_SKILL_DIR}/notify.py" send "text" --title "Day Trader"
python3 "${CLAUDE_SKILL_DIR}/notify.py" send --file trader/reports/brief.txt --key brief-2026-11-24
python3 "${CLAUDE_SKILL_DIR}/notify.py" send "text" --dry-run        # show, send nothing
```

## Channels

| channel | how | set up |
| --- | --- | --- |
| WhatsApp | `notify.py`, CallMeBot's free API, to the user's own number | `CALLMEBOT_PHONE` (+33...) and `CALLMEBOT_APIKEY` as environment variables |
| Telegram | `notify.py`, the user's bot (the one tradepilot uses) | `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` |
| Google Drive | the Google Drive connector: one Google Doc per run in the "Day Trader" folder (id `1IDmSxTMUCUqw_SHc709QpUPmBm7VBUtJ`) | the session's Google Drive connector |
| E-mail | the Gmail connector, to the user's own address only | the session's Gmail connector |
| Phone push | PushNotification (Claude app), only when a decision is needed | nothing more |

Getting a CallMeBot key: follow https://www.callmebot.com/blog/free-api-whatsapp-messages/
(add the number it gives to the phone's contacts, send it "I allow callmebot to
send me messages" on WhatsApp; the key comes back in a reply). The number
changes from time to time, so always take it from that page. The user then adds both variables in the cloud environment's
settings (environment menu, Edit, environment variables). Never ask for the key
or the token in the chat, never write them to a file, never print them.

If `notify.py status` says a channel is not set up, say so once in the run's
summary and carry on with the channels that work. Exit code 3 means none is set
up; that is not an error for the rest of the run.

## What a notification says

- **One screen.** Lead with what needs a decision, then what changed. A
  WhatsApp message over 1,500 characters is split in numbered parts; keep it
  under that.
- **Facts with their source and time (New York time).** "TSLA +11.5 % vs
  yesterday's close, 9:45 ET. 8-K filed 8:10 ET: officer change." Never a
  prediction, never "buy".
- **Once.** Use `--key` with the event and the date (`orb-2026-11-24-TSLA`,
  `stop-2026-11-24-TSLA`, `pelosi-20035780`) so an hourly run does not repeat
  itself. Nothing new: send nothing (the Drive report still records the run).
- **Never** a key, a token, a phone number, an account number, or a
  ready-to-send order. Orders go through /trader-risk and /trader-broker, with
  the user's typed yes, in a conversation.
- End with: "Not financial advice."

## Drive report

One Google Doc per run, titled `YYYY-MM-DD HH:MM ET - <agent>` in the
"Day Trader" folder (search it by name if the id above is gone; create it only
if it is missing). Body: the same summary
as the notification, then the full tool output (scanner hits, news items with
links, plans, Time Machine odds, risk verdicts). Search for the folder by name
before creating it so there is only ever one.
