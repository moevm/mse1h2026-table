set -euo pipefail

HOST="${1:-http://localhost:8088}"
RESULTS_DIR="results"
mkdir -p "$RESULTS_DIR"

echo "httpbin demo runner (issue #88)"
echo " Target host : $HOST"
echo " Results dir : $RESULTS_DIR"
echo ""

echo "[1/2] single_request — 50 users"
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
echo "-> $RESULTS_DIR/single_*.csv, single_report.html"

echo "[2/2] chain — 30 users"
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
echo "-> $RESULTS_DIR/chain_*.csv, chain_report.html"

echo ""
ls -lh "$RESULTS_DIR"
