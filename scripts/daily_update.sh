#!/bin/zsh
# Daily after-close data update. Scheduled by ~/Library/LaunchAgents/com.optionlab.daily-update.plist.
# Credentials are read from ENV_FILE by the Python scripts and never printed; Shioaji output is
# filtered before it reaches the log.
# Machine-specific paths (DATA, ENV_FILE, WTOX) live in scripts/daily_update.local, which is
# git-ignored; copy scripts/daily_update.local.example to create it.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
LOCAL_CONF="$REPO/scripts/daily_update.local"
if [[ ! -f "$LOCAL_CONF" ]]; then
    echo "Missing $LOCAL_CONF (copy scripts/daily_update.local.example and fill in your paths)" >&2
    exit 1
fi
source "$LOCAL_CONF"
: "${DATA:?set DATA in daily_update.local}" "${ENV_FILE:?set ENV_FILE in daily_update.local}" "${WTOX:?set WTOX in daily_update.local}"
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
(cd "$WTOX" && run "$WTOX/.venv/bin/python" -m wtox.research.trades --data "$DATA" --out "$DATA/panel/tsmc_warrant_trades")

echo "\n== done ($(date +%T))" >> "$LOG"
# keep 60 days of logs
find "$LOG_DIR" -name 'daily_*.log' -mtime +60 -delete
