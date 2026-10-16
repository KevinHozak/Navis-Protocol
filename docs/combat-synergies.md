# Active squad combat synergies

Combat reads deployed members from `Bridge/status.json`'s `squad` array.
Vanguard is a role within that array, so its member contributes once. Duplicate
names contribute once; Keeper and reserve companions do not contribute.

Bundled companion schemas in `backend/data/companion_combat.json` give Groza
20% extra Shield, Lyra 1 extra AP each turn, and Rita 15% extra Kinetic damage.
An optional `Companions/<name>/Combat.json` overrides that companion's defaults:

```json
{"passives": {"shield_percent": 20, "ap_bonus": 1, "kinetic_percent": 15}}
```

Missing profiles for other companions grant no buffs. An empty `passives` object
disables a default. Values must be non-negative integers; percent bonuses are
limited to 100 per companion, AP to 10. Unknown keys and invalid values fail
before task writes. Request payloads cannot choose companions or profile paths.
No personal Vault migration is required.

Bonuses from distinct companions add. Shield increases the combined round shield;
Kinetic increases each Kinetic card's attack before debuff and target allocation.
Percent results round down. Other elements retain their base attack. Lyra's AP
draw means one extra action point in the refreshed per-turn budget; it does not
draw another card. The base `ap_per_turn` remains unchanged, preventing repeated
hydration from compounding the bonus.

State responses expose current `encounter.synergies` and `ap_available`.
CombatTheater adds an animated aura and accessible passive labels to contributing
companion portraits during an encounter. Recall and replacement refresh the
preview. Each prepared resolution saves its exact synergy snapshot; recovery
and replay retain that calculation even if the squad changes. The next new
round uses the newly deployed squad. HTTP and the native Python combat bridge
share the same profile reads and evaluation.
