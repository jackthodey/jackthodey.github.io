---
name: run-family-quiz
description: Build, run, start, and smoke-test the family-quiz Flask app. Use when asked to start the family-quiz server, verify it works, test its API endpoints, check that submissions or the leaderboard are correct, or confirm a change is working.
---

Family quiz is a Flask/Python web server (port 5001 in dev). Agents drive it
via `curl` — no browser needed. The smoke script
`.claude/skills/run-family-quiz/smoke.sh` launches the server, hits every
endpoint, asserts correctness, and stops cleanly. Run it from `family-quiz/`.

All paths below are relative to `family-quiz/`.

## Prerequisites

Python 3.11+ and the packages in `requirements.txt`. No system packages
beyond a standard Python environment are needed.

```bash
pip install -r requirements.txt
```

## Run (agent path)

Run the smoke script — it starts the server, exercises every endpoint, and
exits 0 if all checks pass:

```bash
bash .claude/skills/run-family-quiz/smoke.sh
```

Expected output (all green):

```
✓ server up
✓ /api/config
✓ /api/submit El 20/25
✓ /api/submit Jack 18/25
✓ /api/submission (existing entry)
✓ /api/results (family combined 23/25)
✓ /api/leaderboard
✓ DELETE /api/submission
✓ /api/weeks

All checks passed. Log: /tmp/family-quiz.log
```

Logs → `/tmp/family-quiz.log`. The script cleans up the server process and
test database on exit.

### Manual curl against a running server

Start the server in the background (port 5001):

```bash
rm -f data/quiz.db
python3 app.py > /tmp/family-quiz.log 2>&1 &
sleep 3
```

Key endpoints:

```bash
# App config (players, question count)
curl -s http://localhost:5001/api/config

# Submit a player's right/wrong results
curl -s -X POST http://localhost:5001/api/submit \
  -H 'Content-Type: application/json' \
  -d '{"name":"El","week_id":"2026-06-22","results":[true,true,false,...]}'

# Fetch a player's existing entry for a week (for pre-fill / re-entry)
curl -s http://localhost:5001/api/submission/2026-06-22/El

# Weekly leaderboard + family "best-of" combined score
curl -s http://localhost:5001/api/results/2026-06-22

# All-time leaderboard
curl -s http://localhost:5001/api/leaderboard

# Recent weeks with submissions
curl -s http://localhost:5001/api/weeks

# Clear a player's entry for a week (they can then re-enter)
curl -s -X DELETE http://localhost:5001/api/submission/2026-06-22/El
```

Stop:

```bash
pkill -f "python3 app.py"
```

## Run (human path)

```bash
python3 app.py   # → http://127.0.0.1:5001  Ctrl-C to stop
```

Opens the quiz UI in the browser. The UI shows a week dropdown (Sundays
only, last 8 weeks), player selector, and a 25-question right/wrong grid.

## Gotchas

- **Port 5001, not 5000.** Flask defaults to 5000 but `app.py` explicitly
  sets 5001 via `app.run(port=5001)`.
- **SQLite file is ephemeral on Render free tier.** `data/quiz.db` lives
  on the container's local filesystem and is wiped on every new deploy.
  For persistent history, wire up an external Postgres instance.
- **The smoke script wipes `data/quiz.db` on start and on exit.** Don't
  run it against a server holding real data.
- **Production deploy uses gunicorn, not the dev server.** Start command
  on Render is `gunicorn app:app` with Root Directory set to `family-quiz`.

## Troubleshooting

- **`No module named 'flask'`**: run `pip install -r requirements.txt` from
  inside `family-quiz/`.
- **`Address already in use`**: another instance is running — `pkill -f
  "python3 app.py"` then retry.
- **Render build fails with `requirements.txt not found`**: Root Directory
  is not set to `family-quiz` in the Render service settings.
