#!/bin/bash
# Vida Wallet Mainnet Testing Helper
# Quick access to all mainnet testing capabilities

set -e

WALLET_PATH="$HOME/.hermes/projects/vida/vida_owner_secure.json"
PROJECT_DIR="$HOME/.hermes/projects/vida-release"

echo "🔐 Vida Wallet Mainnet Testing Suite"
echo "📁 Project: $PROJECT_DIR"
echo "💰 Wallet: $WALLET_PATH"
echo ""

if [[ ! -f "$WALLET_PATH" ]]; then
    echo "❌ Mainnet wallet not found at $WALLET_PATH"
    echo "💡 Create one with: python scripts/create_mainnet_wallet.py"
    exit 1
fi

cd "$PROJECT_DIR"

echo "Available commands:"
echo "  1. paper     - Advanced paper trading simulation"
echo "  2. dust      - Live dust transaction test (REAL MONEY)"
echo "  3. create    - Create new mainnet wallet"
echo "  4. status    - View test results and status"
echo "  5. help      - Show detailed help"
echo ""

read -p "Choose option [1-5]: " choice

case $choice in
    1)
        echo "🧪 Running advanced paper trading simulation..."
        python scripts/advanced_paper_trading.py
        ;;
    2)
        echo "⚠️  LIVE DUST TEST - This uses REAL mainnet KAS!"
        echo "💰 Amount: 0.03 KAS (~$0.01)"
        echo "🔥 Funds will be BURNED (irreversible)"
        echo ""
        read -p "Continue with live test? [y/N]: " confirm
        if [[ "$confirm" =~ ^[Yy]$ ]]; then
            python scripts/dust_test.py --wallet-path "$WALLET_PATH" --amount 0.03
        else
            echo "❌ Cancelled"
        fi
        ;;
    3)
        echo "🔑 Creating new mainnet wallet..."
        python scripts/create_mainnet_wallet.py
        ;;
    4)
        echo "📊 Vida Wallet Mainnet Status"
        echo ""
        if [[ -f "MAINNET_READINESS_REPORT.md" ]]; then
            head -30 MAINNET_READINESS_REPORT.md
            echo ""
            echo "📖 Full report: MAINNET_READINESS_REPORT.md"
        else
            echo "❌ No status report found"
        fi
        
        echo ""
        echo "Recent test results:"
        ls -la test_results/ 2>/dev/null | tail -5 || echo "No test results found"
        ;;
    5)
        echo "📖 Vida Wallet Mainnet Testing Help"
        echo ""
        echo "PAPER TRADING:"
        echo "  python scripts/advanced_paper_trading.py"
        echo "  - Comprehensive simulation testing"
        echo "  - No real money involved"
        echo "  - Tests all edge cases"
        echo ""
        echo "DUST TESTING:"
        echo "  python scripts/dust_test.py --wallet-path PATH --amount 0.03"
        echo "  - Uses REAL mainnet KAS"
        echo "  - Burns small amount (~$0.01)"
        echo "  - Validates full transaction flow"
        echo ""
        echo "WALLET CREATION:"
        echo "  python scripts/create_mainnet_wallet.py"
        echo "  - Interactive wallet setup"
        echo "  - Generates secure mainnet wallet"
        echo "  - Requires password protection"
        echo ""
        echo "FILES:"
        echo "  MAINNET_READINESS_REPORT.md - Comprehensive status report"
        echo "  MAINNET_STATUS.md - Current testing status"
        echo "  test_results/ - Detailed test output"
        ;;
    *)
        echo "❌ Invalid option"
        exit 1
        ;;
esac

echo ""
echo "✅ Complete"