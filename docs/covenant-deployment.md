# Covenant Deployment Guide

This document outlines the process for deploying covenants to the Kaspa mainnet using Vida.

## Prerequisites

1. **Kaspa Node**: Ensure you have a synced Kaspa node running with RPC enabled.
2. **Vida Wallet**: Use `secure_wallet.py` (not `wallet.py`) for real funds.
3. **SilverScript**: Compile your covenant script to SilverScript bytecode.
4. **Environment Variables**: Set `KASPA_RPC_URL` and `VIDA_FEE_ADDRESS`.

## Deployment Steps

1. **Compile Covenant**:
   ```bash
   cd vida/plugins/covenant/silverscript
   python compile.py your_contract.ss
   ```
   This generates `your_contract.ssc` (compiled bytecode).

2. **Fund Deployment UTXO**:
   - Send enough KAS to cover the deployment fee (typically 0.1 KAS) to a dedicated UTXO.
   - Note the UTXO's `txid` and `vout`.

3. **Deploy Covenant**:
   ```python
   from vida.plugins.covenant.sdk_integration import deploy_covenant

   txid = deploy_covenant(
       contract_path="your_contract.ssc",
       funding_txid="your_utxo_txid",
       funding_vout=0,  # UTXO index
       fee_rate=1.0,    # sat/byte
   )
   print(f"Deployed covenant TXID: {txid}")
   ```

4. **Verify Deployment**:
   - Wait for 6 confirmations.
   - Check the covenant's status:
     ```python
     from vida.plugins.covenant.tools import get_covenant_status
     status = get_covenant_status(txid)
     print(status)
     ```

## Best Practices

- **Test on Testnet**: Always deploy to Kaspa testnet-10 first.
- **Monitor Fees**: Adjust `fee_rate` based on network congestion.
- **Security**: Use multi-sig for high-value covenants.

## Troubleshooting

- **RPC Errors**: Ensure your node is synced and RPC is accessible.
- **Insufficient Funds**: Check the UTXO has enough KAS for fees.
- **Script Errors**: Verify the SilverScript compiles without errors.

## Example Deployment

```python
# Example: Deploy an escrow covenant
txid = deploy_covenant(
    contract_path="escrow.ssc",
    funding_txid="abc123...",
    funding_vout=0,
    fee_rate=1.5,
)
```