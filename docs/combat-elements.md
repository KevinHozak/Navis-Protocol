# Elemental combat profiles

An optional `Codex/Beasts/<beast name>/Combat.json` defines a beast's elemental
profile. Existing `Obstacles/Beasts/<beast name>/Combat.json` profiles are also
supported; Codex takes precedence. Encounter enemies identify the profile with
`beast`, falling back to `id`. Missing profiles use the server-owned enemy fields.

```json
{"affinity": "Void", "vulnerabilities": {"Digital": 2, "Kinetic": 1.5}}
```

Elements are Physical, Digital, Kinetic, Arcane and Void. Vulnerabilities can also
be a list of element names, each granting a 2× multiplier. Explicit multipliers
must be finite numbers greater than 1 and at most 10. Affinity describes the beast;
it does not create an implicit weakness. Invalid profiles fail before task writes.
Cards specify `element`; a recognized elemental `type` is also supported. Legacy
cards default to Physical. Legacy beasts have no weaknesses.

Damage, AP and shields follow the tactical turn rules. An attacking card that
actually deals damage to a living vulnerable target earns a critical XP multiplier.
Debuffed attacks, shields and unused overkill do not earn critical bonuses. The
largest matching multiplier applies once per completed task; bonuses do not stack.

The normal checked-task award remains 2 XP. A separate Keeper ledger entry awards
`floor(2 × (multiplier - 1))` additional XP; daily and companion awards retain their
existing rules. Fractional bonuses round down. The round and exact bonus event are
saved before task mutation. `combat:<resolution_id>:keeper:critical` uniquely
identifies the award in `Keeper/navis_progression.db`, with matched cards, targets
and multiplier in provenance. Recovery reuses that event, including its timestamp,
and repairs projections without duplicating the award.

CombatTheater displays enemy affinity/weaknesses, potential hand-card advantages,
and the last round's confirmed critical multiplier. Native and HTTP combat use
the same evaluation and completion service.
