# Issue #187: historical Bestiary

No user review is required for implementation. This is an additive HUD and
read-only projection, with combat writes restricted to the existing recoverable
completion pipeline. Fixtures use temporary Vaults only.

## Acceptance criteria and implementation

- Persist replay-safe tactical round snapshots in Keeper/navis_progression.db.
  Aggregate by beast and encounter; use terminal outcomes for rates and actual
  HP loss for best turn damage. Do not infer missing legacy history from XP.
- Combine catalog profiles from Codex/Beasts and Obstacles/Beasts with history.
  Display affinity, vulnerabilities, encounter frequency, slayings and derived
  trophy thresholds. Preserve existing profile and Forge navigation.
- Weekly Holocron threat buttons navigate to the Codex Beasts dashboard and
  highlight/scroll to the named entry. Cached Holocrons fall back to beast name.
- Route desktop Bestiary reads through the local Python combat adapter; include
  the service in packaged resources. No HTTP service is needed.

## Verification

Synthetic tests cover multi-round aggregation, win/defeat/active rates, actual
damage versus overkill, replay conflicts, legacy databases, invalid profiles,
and completion/read parity through backend, HTTP and native subprocess adapters.
Run affected combat and Holocron suites, client regressions, frontend compilation,
and native compilation when the host dependencies allow it.
