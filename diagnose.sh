#!/bin/bash
# ============================================================
# SwingEdge Pro — Diagnostic Script
# Run this to find why the Leveraged ETF screen shows "Error loading"
# ============================================================
#
# USAGE: bash diagnose.sh
# Run this AFTER starting the server.
# ============================================================

echo "========================================"
echo "  SwingEdge Pro — Diagnostic"
echo "========================================"
echo ""

BASE_URL="http://localhost:8000"

# Test 1: Server running?
echo "[1/8] Checking if server is running on port 8000..."
if curl -sf "$BASE_URL/api/health" > /dev/null 2>&1; then
    echo "  ✅ Server is running"
    curl -s "$BASE_URL/api/health" | python3 -m json.tool 2>/dev/null || curl -s "$BASE_URL/api/health"
else
    echo "  ❌ Server is NOT running on port 8000"
    echo "  Fix: cd swing-edge-pro && python -m uvicorn backend.main:app --port 8000 --reload"
    exit 1
fi
echo ""

# Test 2: Leveraged ETF router registered?
echo "[2/8] Checking if leveraged-etfs router is registered..."
LEVERAGED_HEALTH=$(curl -s "$BASE_URL/api/leveraged-etfs/universe/summary" 2>&1)
if echo "$LEVERAGED_HEALTH" | grep -q "total_etfs"; then
    echo "  ✅ Router is registered"
    echo "  $LEVERAGED_HEALTH"
else
    echo "  ❌ Router NOT registered or returned error"
    echo "  Response: $LEVERAGED_HEALTH"
    echo ""
    echo "  This means the server is running an OLD version of the code."
    echo "  Fix: Pull the latest code and RESTART the server."
    exit 1
fi
echo ""

# Test 3: Screen endpoint
echo "[3/8] Testing screen endpoint..."
SCREEN=$(curl -s "$BASE_URL/api/leveraged-etfs?min_score=0&limit=5" 2>&1)
if echo "$SCREEN" | grep -q "signals"; then
    COUNT=$(echo "$SCREEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('count',0))" 2>/dev/null || echo "?")
    echo "  ✅ Screen endpoint works. Count: $COUNT"
    if echo "$SCREEN" | grep -q "error"; then
        echo "  ⚠️  But there's an error in the response:"
        echo "$SCREEN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('error',''))" 2>/dev/null
    fi
else
    echo "  ❌ Screen endpoint returned error:"
    echo "  $SCREEN" | head -5
fi
echo ""

# Test 4: Regime
echo "[4/8] Checking market regime..."
REGIME=$(curl -s "$BASE_URL/api/market-pulse" 2>&1)
echo "  $REGIME" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'VIX: {d.get(\"vix\")}, Quality: {d.get(\"data_quality\")}')" 2>/dev/null || echo "  $REGIME" | head -3
echo ""

# Test 5: Check server logs for errors
echo "[5/8] Checking for Python import errors..."
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from backend.routers.leveraged_etfs import router
    print('  ✅ leveraged_etfs router imports OK')
except Exception as e:
    print(f'  ❌ Import error: {e}')
try:
    from backend.engine.leveraged_etf import LeveragedETFEngine
    print('  ✅ LeveragedETFEngine imports OK')
except Exception as e:
    print(f'  ❌ Import error: {e}')
try:
    from backend.engine.scoring import MasterScorer
    print('  ✅ MasterScorer imports OK')
except Exception as e:
    print(f'  ❌ Import error: {e}')
" 2>&1
echo ""

# Test 6: Frontend files exist?
echo "[6/8] Checking frontend files..."
for f in leveraged_etfs.html js/leveraged_etfs.js; do
    if [ -f "frontend/$f" ]; then
        echo "  ✅ frontend/$f exists"
    else
        echo "  ❌ frontend/$f MISSING"
    fi
done
echo ""

# Test 7: Sidebar link in index.html?
echo "[7/8] Checking sidebar in index.html..."
if grep -q "leveraged_etfs.html" frontend/index.html 2>/dev/null; then
    echo "  ✅ index.html has leveraged ETFs sidebar link"
else
    echo "  ❌ index.html is MISSING the leveraged ETFs sidebar link"
    echo "  This is why one page has 'Leverage' in sidebar and another doesn't."
fi
echo ""

# Test 8: All HTML files have sidebar?
echo "[8/8] Checking all HTML files for sidebar consistency..."
for f in frontend/*.html; do
    if grep -q "leveraged_etfs.html" "$f"; then
        echo "  ✅ $f"
    else
        echo "  ❌ $f — MISSING sidebar link"
    fi
done
echo ""

echo "========================================"
echo "  Diagnostic complete."
echo "========================================"
echo ""
echo "If you see any ❌ above, that's what needs fixing."
echo "Most common fix: pull latest code + RESTART server."
echo ""
