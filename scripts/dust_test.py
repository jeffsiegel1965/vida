#!/usr/bin/env python3
"""
Vida Wallet Dust Transaction Test

Phase 2: Real mainnet dust transactions using Vida's transaction system
- Requires funded wallet
- Tests with minimal amounts (above dust threshold but still tiny)
- Full transaction lifecycle validation
- Comprehensive safety checks

Usage:
    python scripts/dust_test.py --wallet-path ~/.vida/wallets/test.json --amount 0.03
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DustTransactionTest:
    """Real mainnet dust transaction testing."""
    
    def __init__(self, wallet_path: str, amount: str = "0.03"):
        self.wallet_path = Path(wallet_path)
        self.amount_kas = float(amount)  # Use float for Vida compatibility
        
    def safety_checks(self) -> bool:
        """Pre-flight safety validation."""
        logger.info("🔒 Running safety checks...")
        
        # Check 1: Amount is truly dust (< $0.01 USD assuming $0.10/KAS)
        usd_value = self.amount_kas * 0.10  # Conservative KAS price
        if usd_value > 0.01:
            logger.error(f"❌ Amount too large: ${usd_value:.4f} USD (max $0.01)")
            return False
        logger.info(f"✅ Dust amount confirmed: {self.amount_kas} KAS (~${usd_value:.4f})")
        
        # Check 2: Wallet file exists
        if not self.wallet_path.exists():
            logger.error(f"❌ Wallet not found: {self.wallet_path}")
            return False
        logger.info(f"✅ Wallet found: {self.wallet_path}")
        
        # Check 3: Amount is above dust threshold but still tiny
        if self.amount_kas < 0.02:  # Below Kaspa dust threshold
            logger.error(f"❌ Amount {self.amount_kas} KAS below Kaspa dust threshold (0.02 KAS)")
            return False
        if self.amount_kas > 0.1:  # Above our test threshold
            logger.error(f"❌ Amount {self.amount_kas} KAS too large for dust test (max 0.1 KAS)")
            return False
        logger.info(f"✅ Amount within safe dust test range: {self.amount_kas} KAS")
        
        return True
    
    async def run_dust_test(self) -> bool:
        """Run complete dust transaction test."""
        logger.info("🧪 Starting dust transaction test...")
        
        # Safety checks
        if not self.safety_checks():
            return False
        
        try:
            from vida.secure_wallet import SecureVida
            from vida.transactions import VidaTransactor
            
            # Load wallet
            logger.info("🔑 Loading Vida wallet...")
            vida = SecureVida(str(self.wallet_path))  # No network parameter - it's in the file
            
            # Create transactor
            transactor = VidaTransactor(vida)
            
            # Connect to network
            logger.info("🌐 Connecting to network...")
            await transactor.connect()
            
            # Get current balance
            logger.info("💰 Checking balance...")
            balance_kas = await transactor.get_balance()  # Returns float directly
            logger.info(f"Current balance: {balance_kas} KAS")
            
            # Validate sufficient funds
            if balance_kas < (self.amount_kas + 0.01):  # Amount + fee buffer
                logger.error(f"❌ Insufficient funds: {balance_kas} < {self.amount_kas + 0.01} KAS required")
                return False
            
            logger.info(f"✅ Sufficient funds: {balance_kas} KAS")
            
            # For dust test, send to a burn address (irreversible but safe)
            burn_address = "kaspa:qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqz7ffns3khf2wh"
            
            # Final confirmation
            logger.warning("🚨 BROADCASTING TO MAINNET - REAL FUNDS AT RISK!")
            logger.info("Transaction details:")
            logger.info(f"  From: {vida.address}")
            logger.info(f"  To: {burn_address} (BURN ADDRESS - IRREVERSIBLE)")
            logger.info(f"  Amount: {self.amount_kas} KAS")
            logger.info(f"  Network: mainnet")
            
            response = input("\n🔥 FINAL CONFIRMATION - This will BURN real KAS on mainnet. Type 'BURN' to continue: ")
            if response != "BURN":
                logger.info("❌ Test cancelled by user")
                return False
            
            # Execute the transaction
            logger.info("📡 Broadcasting transaction...")
            result = await transactor.send(
                to_address=burn_address,
                amount_kas=self.amount_kas,
                confirm=True  # Required for agent session spends
            )
            
            if result.success:
                logger.info("🎉 Transaction broadcasted successfully!")
                logger.info(f"Transaction ID: {result.txid}")
                logger.info(f"Amount sent: {result.amount_kas} KAS")
                logger.info(f"Fee paid: {result.fee_kas} KAS")
                logger.info(f"Network verified: {result.verified_on_network}")
                logger.info(f"Explorer: {result.explorer_url}")
                
                # Save transaction record
                self._save_transaction_record(result)
                
                logger.info("🎉 Dust transaction test completed successfully!")
                return True
            else:
                logger.error(f"❌ Transaction failed: {result.error}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Test exception: {e}")
            return False
    
    def _save_transaction_record(self, result):
        """Save transaction record for audit trail."""
        records_dir = ROOT / "test_results" / "transactions"
        records_dir.mkdir(parents=True, exist_ok=True)
        
        record = {
            "timestamp": time.time(),
            "network": result.network,
            "test_type": "dust_transaction",
            "success": result.success,
            "txid": result.txid,
            "amount_kas": result.amount_kas,
            "fee_kas": result.fee_kas,
            "to_address": result.to_address,
            "verified_on_network": result.verified_on_network,
            "explorer_url": result.explorer_url
        }
        
        if result.txid:
            record_file = records_dir / f"dust_tx_{result.txid}.json"
        else:
            record_file = records_dir / f"dust_tx_failed_{int(time.time())}.json"
        
        with open(record_file, 'w') as f:
            json.dump(record, f, indent=2, default=str)
            
        logger.info(f"💾 Transaction record saved: {record_file}")


def main():
    parser = argparse.ArgumentParser(description="Vida Wallet Dust Transaction Test")
    parser.add_argument("--wallet-path", required=True,
                       help="Path to Vida wallet JSON file")
    parser.add_argument("--amount", default="0.03", 
                       help="Amount to send (KAS, min 0.02, max 0.1)")
    
    args = parser.parse_args()
    
    # Validate amount is within safe range
    try:
        amount = float(args.amount)
        if amount < 0.02:
            logger.error("❌ Amount too small (below Kaspa dust threshold 0.02 KAS)")
            sys.exit(1)
        if amount > 0.1:
            logger.error("❌ Amount too large for dust test (max 0.1 KAS)")
            sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Invalid amount: {e}")
        sys.exit(1)
    
    # Run test
    tester = DustTransactionTest(args.wallet_path, args.amount)
    success = asyncio.run(tester.run_dust_test())
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()