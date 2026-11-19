#!/bin/zsh
# Daily after-close data update. Scheduled by ~/Library/LaunchAgents/com.optionlab.daily-update.plist.
# Credentials are read from ENV_FILE by the Python scripts and never printed; Shioaji output is
# filtered before it reaches the log.
set -u
REPO="/Users/a000/Desktop/權證/Option-Analysis-System"
DATA="/Users/a000/Desktop/權證/data"
ENV_FILE="/Users/a000/Desktop/SinoPac Trading/.env"
PY="$REPO/.venv/bin/python"
LOG_DIR="$DATA/logs"
TODAY=$(date +%F)
LOG="$LOG_DIR/daily_$TODAY.log"
FILTER='key|secret|token|passw|Response Code|P2P|Event|session|ca_path'

mkdir -p "$LOG_DIR"
cd "$REPO" || exit 1
step() { echo "\n== $1 ($(date +%T))" >> "$LOG"; }
run() { "$@" 2>&1 | grep -v -iE "$FILTER" >> "$LOG"; }

step "TWSE warrant terms"
run "$PY" -m optcore.data.twse --out "$DATA/twse"

step "TSMC warrants (kbars + ticks)"
run "$PY" -u -m optcore.data.shioaji_source --underlying 2330 --out "$DATA/shioaji" --env-file "$ENV_FILE" \
    --underlying-start 2025-11-12 --warrant-kbar-days 95 --tick-days 63 --tick-top 1300 --max-mb 300

step "2330 stock / CDF / TXF ticks"
run "$PY" -u scripts/fetch_underlying_ticks.py --data "$DATA" --env-file "$ENV_FILE"

step "TXF / MXF / TMF R1+R2 minute bars"
run "$PY" -u scripts/fetch_futures_r1r2.py --root "$DATA/futures_continuous" --env-file "$ENV_FILE" --end "$TODAY"

step "Extend continuous futures series"
run "$PY" scripts/extend_futures_continuous.py --root "$DATA/futures_continuous" --end "$TODAY"

step "Rebuild TSMC warrant trade panel (new days only)"
# the panel builder lives in the standalone warrant-toxicity repo
WTOX="/Users/a000/Desktop/權證/warrant-toxicity"
(cd "$WTOX" && run "$WTOX/.venv/bin/python" -m wtox.research.trades --data "$DATA" --out "$DATA/panel/tsmc_warrant_trades")

echo "\n== done ($(date +%T))" >> "$LOG"
# keep 60 days of logs
find "$LOG_DIR" -name 'daily_*.log' -mtime +60 -delete
