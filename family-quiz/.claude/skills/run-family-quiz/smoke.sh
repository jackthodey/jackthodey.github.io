#!/usr/bin/env bash
# smoke.sh — launch family-quiz, verify every API endpoint, stop cleanly.
# Run from the family-quiz/ directory.
# Exit 0 = healthy. Exit 1 = something broke (check /tmp/family-quiz.log).

set -euo pipefail

PORT=5001
LOG=/tmp/family-quiz.log
DB=data/quiz.db

cleanup() { pkill -f "python3 app.py" 2>/dev/null || true; rm -f "$DB"; }
trap cleanup EXIT

rm -f "$DB"
python3 app.py >"$LOG" 2>&1 &
APP_PID=$!

# Wait for server to be ready (up to 15s)
for i in $(seq 1 30); do
  curl -sf "http://localhost:$PORT/" >/dev/null 2>&1 && break
  sleep 0.5
done
curl -sf "http://localhost:$PORT/" >/dev/null || { echo "FAIL: server did not come up"; exit 1; }

echo "✓ server up"

# /api/config
OUT=$(curl -sf "http://localhost:$PORT/api/config")
echo "$OUT" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['question_count']==25" \
  || { echo "FAIL: /api/config"; exit 1; }
echo "✓ /api/config"

# /api/submit — two players
R1=$(python3 -c 'import json; print(json.dumps([True]*20+[False]*5))')
R2=$(python3 -c 'import json; print(json.dumps([True]*15+[False]*5+[True]*3+[False]*2))')
WEEK="2026-06-22"

curl -sf -X POST "http://localhost:$PORT/api/submit" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"El\",\"week_id\":\"$WEEK\",\"results\":$R1}" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); assert d['score']==20" \
  || { echo "FAIL: /api/submit El"; exit 1; }
echo "✓ /api/submit El 20/25"

curl -sf -X POST "http://localhost:$PORT/api/submit" \
  -H 'Content-Type: application/json' \
  -d "{\"name\":\"Jack\",\"week_id\":\"$WEEK\",\"results\":$R2}" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); assert d['score']==18" \
  || { echo "FAIL: /api/submit Jack"; exit 1; }
echo "✓ /api/submit Jack 18/25"

# /api/submission/<week>/<name> — fetch existing
curl -sf "http://localhost:$PORT/api/submission/$WEEK/El" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); assert d['existing']['score']==20" \
  || { echo "FAIL: /api/submission"; exit 1; }
echo "✓ /api/submission (existing entry)"

# /api/results — weekly leaderboard + family combined
curl -sf "http://localhost:$PORT/api/results/$WEEK" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); assert d['family']['score']==23" \
  || { echo "FAIL: /api/results"; exit 1; }
echo "✓ /api/results (family combined 23/25)"

# /api/leaderboard
curl -sf "http://localhost:$PORT/api/leaderboard" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d['leaderboard'])==2" \
  || { echo "FAIL: /api/leaderboard"; exit 1; }
echo "✓ /api/leaderboard"

# DELETE /api/submission — clear entry
curl -sf -X DELETE "http://localhost:$PORT/api/submission/$WEEK/El" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); assert d['cleared']" \
  || { echo "FAIL: DELETE /api/submission"; exit 1; }
curl -sf "http://localhost:$PORT/api/submission/$WEEK/El" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); assert d['existing'] is None" \
  || { echo "FAIL: submission not cleared"; exit 1; }
echo "✓ DELETE /api/submission"

# /api/weeks
curl -sf "http://localhost:$PORT/api/weeks" | \
  python3 -c "import sys,json; d=json.load(sys.stdin); assert '$WEEK' in d['weeks']" \
  || { echo "FAIL: /api/weeks"; exit 1; }
echo "✓ /api/weeks"

echo ""
echo "All checks passed. Log: $LOG"
