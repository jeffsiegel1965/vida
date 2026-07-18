# SilverScript Quine Agent Pot

## Files

| File | Purpose |
|------|---------|
| `quine_agent_pot.sil` | SilverScript source — self-replicating covenant with spend limits |
| `quine_agent_pot.json` | Compiled artifact (ABI + bytecode placeholder) |
| `quine_args.json` | Constructor arguments (pubkey + maxTxSompi) |

## Compile

```bash
cd vida/plugins/covenant/silverscript
silverc quine_agent_pot.sil --constructor-args quine_args.json
```

## Debug

```bash
cli-debugger quine_agent_pot.sil \
  --ctor-arg "<32-byte-pubkey-hex>" \
  --ctor-arg "<maxTxSompi>" \
  --function withdraw \
  --arg "<recipient-pubkey-hex>"
```

## Contract Logic

- `withdraw(pubkey recipient)` — External payment ≤ maxTxSompi to recipient P2PK, covenant self-replicates
- `burn(sig ownerSig)` — Owner-only burn after generation limit reached

## Toccata Resources

| Resource | URL |
|----------|-----|
| Toccata Book | docs.kaspa.org/toccata |
| SilverScript | github.com/kaspanet/silverscript |
| Parker's vault | @parker2017 on X |
| KII quine | covenant b802c18b... on mainnet |
