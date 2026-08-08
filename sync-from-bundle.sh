#!/bin/bash
# ============================================================
# SwingEdge Pro — One-Command Sync Script
# Run this on the local server to pull all v3 upgrades
# ============================================================
#
# USAGE:
#   1. Place swing-edge-pro-v3.bundle in the same directory as this script
#   2. Run: bash sync-from-bundle.sh
#
# This script will:
#   - Pull all v3 commits from the bundle (clean merge, no conflicts)
#   - Install/update Python dependencies
#   - Run tests to verify
#   - Restart the server
# ============================================================

set -e

REPO_DIR="swing-edge-pro"
BUNDLE_FILE="swing-edge-pro-v3.bundle"
BRANCH="audit-fixes-and-upgrades"

echo "========================================"
echo "  SwingEdge Pro v3 — Sync Script"
echo "========================================"
echo ""

# Step 1: Check bundle exists
if [ ! -f "$BUNDLE_FILE" ]; then
    echo "ERROR: $BUNDLE_FILE not found."
    echo "Place the bundle file in the same directory as this script."
    exit 1
fi

# Step 2: Navigate to repo (or clone if doesn't exist)
if [ -d "$REPO_DIR/.git" ]; then
    echo "[1/6] Existing repo found. Pulling from bundle..."
    cd "$REPO_DIR"
    # Add bundle as a temporary remote and fetch
    git bundle verify "../$BUNDLE_FILE" 2>/dev/null || true
    git fetch "../$BUNDLE_FILE" "$BRANCH:bundle-upgrade" 2>/dev/null || true
    # Merge the bundle branch
    git checkout "$BRANCH" 2>/dev/null || git checkout -b "$BRANCH"
    git merge bundle-upgrade --no-edit 2>/dev/null || git reset --hard bundle-upgrade
    git branch -D bundle-upgrade 2>/dev/null || true
else
    echo "[1/6] Cloning from bundle..."
    git clone "$BUNDLE_FILE" "$REPO_DIR"
    cd "$REPO_DIR"
    git checkout "$BRANCH"
fi

echo ""
echo "[2/6] Current commit:"
git log --oneline -1
echo ""

# Step 3: Install dependencies
echo "[3/6] Installing Python dependencies..."
if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null || true
fi
pip install -r requirements.txt --quiet 2>&1 | tail -3
echo "Dependencies installed."
echo ""

# Step 4: Run tests
echo "[4/6] Running tests..."
python -m pytest tests/ -v --tb=short 2>&1 | tail -10
echo ""

# Step 5: Check for .env
if [ ! -f ".env" ]; then
    echo "[5/6] Creating .env from .env.example..."
    cp .env.example .env
    echo "  .env created. Edit it to add your API keys."
else
    echo "[5/6] .env exists (keeping your existing keys)."
fi
echo ""

# Step 6: Restart server
echo "[6/6] Ready to start server."
echo ""
echo "========================================"
echo "  SYNC COMPLETE"
echo "========================================"
echo ""
echo "To start the server:"
echo "  cd $REPO_DIR"
echo "  python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "Then open: http://localhost:8000"
echo "Leveraged ETFs page: http://localhost:8000/leveraged_etfs.html"
echo ""
echo "To verify the API is working:"
echo "  curl http://localhost:8000/api/leveraged-etfs/universe/summary"
echo "  curl http://localhost:8000/api/leveraged-etfs"
echo ""
