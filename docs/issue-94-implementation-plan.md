# Issue 94 implementation plan
Actual Forge writes require approval in the product.
- Validate local-first proposal fields, entity names and target paths.
- Bind approval to immutable proposals stored outside the Vault.
- Run controlled Forge scripts in staging, then publish atomically.
- Web background jobs and native JSON stdin use the same service.
- Discard revokes proposals. Approved operations finish atomically even after closing the UI.
- Test temporary Vaults with injected providers and real Forge scripts.
