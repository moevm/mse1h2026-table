set -euo pipefail

HOST="${1:-http://localhost:8080}"
RESULTS_DIR="results"
mkdir -p "$RESULTS_DIR"

echo " Locust headless runner"
echo " Target host : $HOST"
echo " Results dir : $RESULTS_DIR"

echo "[1/3] single_request 50 пользователей"
locust \
  -f scenarios/single_request.py \
  --host "$HOST" \
  --headless \
  --users 50 \
  --spawn-rate 10 \
  --run-time 60s \
  --csv "$RESULTS_DIR/single" \
  --html "$RESULTS_DIR/single_report.html" \
  --exit-code-on-error 0
echo "Готово → $RESULTS_DIR/single_*.csv, single_report.html"

echo "[2/3] chain 30 пользователей"
locust \
  -f scenarios/chain.py \
  --host "$HOST" \
  --headless \
  --users 30 \
  --spawn-rate 5 \
  --run-time 90s \
  --csv "$RESULTS_DIR/chain" \
  --html "$RESULTS_DIR/chain_report.html" \
  --exit-code-on-error 0
echo "Готово → $RESULTS_DIR/chain_*.csv, chain_report.html"

echo "[3/3] stepped_load профиль 50→100→200→300"
locust \
  -f scenarios/stepped_load.py \
  --host "$HOST" \
  --headless \
  --csv "$RESULTS_DIR/stepped" \
  --html "$RESULTS_DIR/stepped_report.html" \
  --exit-code-on-error 0
echo "Готово → $RESULTS_DIR/stepped_*.csv, stepped_report.html"

echo "Артефакты:"
ls -lh "$RESULTS_DIR"