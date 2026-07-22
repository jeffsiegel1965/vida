# Vida Wallet — Backup & Recovery Guide

## What to back up

### Critical (lose this = lose funds)

| File | Purpose | How to back up |
|------|---------|---------------|
| **24-word mnemonic** | Full wallet recovery | Write on paper, store in fireproof safe. Never store digitally. |
| `vida_secure.json` | Encrypted wallet file | Safe to copy anywhere — useless without password |
| `vida_mainnet.json` | Mainnet wallet metadata | Same as above |

### Important (lose this = lose agent state)

| File | Purpose | How to back up |
|------|---------|---------------|
| `~/.vida/memory/<wallet_id>/memory.json` | Agent memory (deals, counterparties) | Encrypted backup, daily cron |
| `~/.vida/negotiation_memory.json` | Negotiation history | Same as above |
| `~/.vida/subscriptions.json` | Recurring pot subscriptions | Same as above |
| TAO account stores | Bittensor staking records | Encrypted backup, daily cron |

### Useful (lose this = reconfigure)

| File | Purpose | How to back up |
|------|---------|---------------|
| `~/.config/vida/` | App configuration | Version-controlled or encrypted backup |
| `pyproject.toml` / `requirements.txt` | Dependency pins | In git (already) |

## Backup Commands

### Full encrypted backup (recommended)

```bash
# Daily: encrypt and archive wallet + agent state
BACKUP_DIR=~/vida-backups
mkdir -p "$BACKUP_DIR"

tar -czf - \
  ~/.hermes/projects/vida/vida_secure.json \
  ~/.hermes/projects/vida/vida_mainnet.json \
  ~/.vida/ \
  2>/dev/null | \
gpg --symmetric --cipher-algo AES256 \
  --output "$BACKUP_DIR/vida-backup-$(date +%Y-%m-%d).tar.gz.gpg"

echo "Backup saved to $BACKUP_DIR/vida-backup-$(date +%Y-%m-%d).tar.gz.gpg"
```

### Partial backup (wallet files only)

```bash
cp ~/.hermes/projects/vida/vida_secure.json ~/vida-backups/
cp ~/.hermes/projects/vida/vida_mainnet.json ~/vida-backups/
```

### Automated daily backup with cron

Add to crontab (`crontab -e`):

```
0 2 * * * /home/jeff-siegel/scripts/backup-vida.sh
```

## Recovery Procedures

### Recover from mnemonic only (worst case)

```bash
# 1. Install Vida
pip install git+https://github.com/jeffsiegel1965/vida.git

# 2. Create new wallet from your 24-word mnemonic
python scripts/setup_owner_wallet.py --mnemonic "your twenty four words here"

# 3. Verify the address matches your records
python scripts/vida_admin.py --status

# 4. Re-grant agent sessions as needed
python scripts/grant_session.py --hours 24 --max-tx 1 --max-day 5
```

### Recover from encrypted backup file

```bash
# 1. Decrypt the backup
gpg --decrypt vida-backup-2026-07-21.tar.gz.gpg > vida-backup.tar.gz

# 2. Extract
tar -xzf vida-backup.tar.gz -C ~/

# 3. Verify wallet loads
python -c "
from vida.secure_wallet import SecureVida
w = SecureVida('~/.hermes/projects/vida/vida_secure.json', password='YOUR_PASSWORD')
print(f'Address: {w.address}')
print(f'Balance: check explorer')
w.lock()
"
```

### Verify backup integrity (do this quarterly)

```bash
# 1. Decrypt to a temp directory
TMPDIR=$(mktemp -d)
gpg --decrypt vida-backup-2026-07-21.tar.gz.gpg | tar -xzf - -C "$TMPDIR"

# 2. Check wallet loads and address matches
python -c "
import json
with open('$TMPDIR/home/jeff-siegel/.hermes/projects/vida/vida_secure.json') as f:
    data = json.load(f)
print(f'Backed up address: {data[\"address\"]}')
# Compare with known address
"

# 3. Clean up
rm -rf "$TMPDIR"
```

## Session File Management

Sessions are ephemeral by design — they expire and should NOT be backed up.

- **Revoke instantly:** Delete the session file (`rm agent_session.json`)
- **Monitor active sessions:** `python scripts/vida_admin.py --sessions`
- **Rotate regularly:** Re-grant sessions weekly; shorter if high-value
- **Never share session files:** They contain signing material

## Operational Checklist

### Before significant mainnet usage:

- [ ] Mnemonic written on paper, stored in fireproof safe
- [ ] Encrypted wallet file backed up to at least 2 locations
- [ ] Backup decryption tested (restore to temp directory)
- [ ] Address verified against explorer
- [ ] Agent session caps reviewed and set appropriately
- [ ] Revocation procedure tested (delete session, verify agent locked out)

### After any wallet operation with funds:

- [ ] Transaction verified on-chain (explorer link saved)
- [ ] Spending within session caps confirmed
- [ ] No unexpected session files present

### Monthly:

- [ ] Backup integrity test (decrypt + verify address)
- [ ] Review active sessions (revoke any stale ones)
- [ ] Update dependencies (`pip install --upgrade -r requirements.txt`)
- [ ] Check for security advisories (`pip-audit -r requirements.txt`)

## Emergency Procedures

### Suspected key compromise

1. **Immediately:** move funds to a new wallet
   ```bash
   python scripts/setup_owner_wallet.py --new
   # Send all funds from old address to new address via explorer
   ```
2. **Revoke all sessions:** `rm ~/.vida/sessions/*.json`
3. **Rotate:** create new wallet, new mnemonic, new backup
4. **Audit:** review transaction history for unauthorized activity

### Lost password (but have mnemonic)

You can always recover with the 24-word mnemonic. The password only protects
the encrypted wallet file at rest — it's not required for recovery.

### Lost both password AND mnemonic

Funds are irrecoverable. This is self-custody. No recovery service exists.
This is why the mnemonic on paper is the single most important backup.

## Security Notes

- **Never store your mnemonic digitally.** Paper only. Fireproof safe.
- **Encrypted backups are safe to store anywhere** (cloud, USB, etc.) — 
  they're AES-256-GCM encrypted and useless without the password.
- **Test your recovery procedure quarterly.** A backup you haven't tested
  is not a backup.
- **Use different passwords for wallet encryption and GPG backup encryption.**
- **The mnemonic IS the wallet.** Anyone with those 24 words controls the funds.
  Treat it accordingly.
