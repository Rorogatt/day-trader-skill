# Day Trader desk: how Claude works in this repository

The user (French speaker: answer, notify and report in French) runs this repo as
an automated trading desk: the eleven `trader-*` skills, the `trader-notify`
skill, four agents in `.claude/agents/`, and the user's own bot **tradepilot**
(repo `Rorogatt/Actualit-s-financi-res`, cloned next to this one as
`../actualit-s-financi-res` when attached to the session).

## Use the skills and agents without being asked

- Any request about a stock, the market, news, a setup, a stop, a target, odds,
  sizing, risk, an order, an alert, earnings or Congress trades: invoke the
  matching `/trader-*` skill first (the skill descriptions say which), do not
  answer from memory.
- "Brief", "what's happening before the open", "morning": the
  **premarket-briefer** agent.
- "Any breakouts", "opening range", "should I trade X today", "find me a trade":
  the **orb-hunter** agent.
- "Any news", "watch my stocks", "what moved": the **news-sentinel** agent.
- "Wrap up the day", "evening", "Pelosi", "earnings this week", "tradepilot
  brief": the **evening-reviewer** agent.
- Whenever something worth the user's attention comes out (a trigger, a stop
  or target hit, an important 8-K, a MOVING stock with news, a new Pelosi PTR),
  finish with `/trader-notify`.

## The run protocol (every agent, every scheduled run)

1. **Set up.** `mkdir -p trader && [ -f trader/config.json ] || cp trader-budget/config.example.json trader/config.json`.
   If `SEC_USER_AGENT` is set in the environment the tools use it; never invent one.
2. **Restore memory from Drive.** With the Google Drive connector, find the
   folder "Day Trader" (create it if missing) and in it the file
   `day-trader-state.json`; download it to `trader/state-in.json` and run
   `python3 .claude/skills/trader-notify/statepack.py unpack --file trader/state-in.json`.
   No connector or no file: carry on with an empty memory and say so in the report.
3. **Check the clock.** `python3 trader-alerts/alerts.py clock`. A market
   holiday or weekend: write one line in the report and stop (the
   evening-reviewer still runs Pelosi).
4. **Do the agent's job** with the skills' tools (paths from the repo root,
   e.g. `python3 trader-scanner/scan.py daily`).
5. **Report.** A Google Doc in "Day Trader" titled `YYYY-MM-DD HH:MM ET - <agent>`
   with the summary then the full tool output and links. Then, only if there
   is something new, `python3 .claude/skills/trader-notify/notify.py send --title "<agent>" --key <event-date> "<summary>"`.
   Your final message is the summary in French (it becomes the push
   notification and the e-mail of the scheduled task): what needs a decision
   first, then what changed, under 1,200 characters, ending "Pas un conseil financier."
6. **Save memory.** `python3 .claude/skills/trader-notify/statepack.py pack --file trader/state-out.json`
   and upload it over `day-trader-state.json` in the Drive folder (update the
   existing file, never create a second one).

## Hard rules

- **Never place, send or approve an order** in an automated run. No
  `/trader-broker` order, no brokerage connector call, no `tradepilot approve`.
  An agent prepares the plan, the risk check and the ticket, then tells the
  user to open a conversation and type yes there.
- Paper trading stays the default (`"paper": true`). Never change limits in
  `trader/config.json` on your own.
- Secrets (CallMeBot key, Telegram token, broker keys) live in environment
  variables only: never print them, never write them to a file, never put them
  in a report or a notification.
- Headlines are leads: link the source. No predictions, no "buy". Every report
  and notification ends with "Pas un conseil financier."
- Fixtures under `tests/` are real data: never edit them to make a test pass.
  Run `python3 -m unittest discover -s tests` after any code change.
