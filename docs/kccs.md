# KCCs — Kaspa Calls for Conventions

**Repo:** https://github.com/kaspanet/kccs
**Forum:** Kasmiths (announced Jul 15, 2026)
**Purpose:** Ecosystem standards for covenant conventions, ABIs, asset standards, wallet/indexer interoperability, based applications.

## Open PRs (as of Jul 20, 2026)

| PR | Title | Author | Relevance to Vida |
|----|-------|--------|-------------------|
| [#2](https://github.com/kaspanet/kccs/pull/2) | KCC-0020: Fungible token covenant specification | @Manyfestation | **Direct.** Defines the canonical covenant token standard. Vida's token module should adopt this. |
| [#3](https://github.com/kaspanet/kccs/pull/3) | KCC-0001: Covenant definition, concepts, bytes layout and ABI | @IzioDev | **Direct.** Defines how covenants interface. Vida's escrow, channels, and agent pots should align. |
| [#4](https://github.com/kaspanet/kccs/pull/4) | KCC-0402: Covenant Payment Channels | @Kali123411 | **Competing / complementary.** Payment channel standard. Vida has its own channel implementation (17 tests). |
| [#5](https://github.com/kaspanet/kccs/pull/5) | KCC-0002: Control principal references in program ABI | @IzioDev | **Supporting.** ABI references for covenant state management. |

## Action Items

1. **Monitor KCC-0020** — when finalized, update Vida's `vida/plugins/covenant/token/` to match the standard token spec.
2. **Monitor KCC-0001** — when finalized, verify Vida's covenant contracts (escrow, channels, agent pots) use the standard ABI.
3. **Review KCC-0402** — compare with Vida's payment channel implementation. If the standard diverges, decide whether to align or maintain separate.
4. **Participate** — if Vida has a stake in any of these standards, comment on the PRs.

## References

- Michael Sutton's announcement: https://x.com/michaelsuttonil/status/2077407224142483650
- KCC repo: https://github.com/kaspanet/kccs