# Combat-P1 tactical rules

Cards expose non-negative integer `ap_cost`, `attack`, and `shield` fields.
Legacy cards default to 1 AP, 0 attack, 0 shield without rewriting the card files.
Both linked cards contribute their stats. An unaffordable maneuver is rejected
before a task, card, or resolution is changed.

An optional server-owned `encounter` in `Battle/battle_state.json` enables rounds:

```json
{"turn":1,"player_hp":100,"ap_per_turn":2,"enemies":[
  {"id":"sentinel","hp":20,"attack":4,"intent_pattern":["Charge","Strike","Debuff"]}
]}
```

Attack is distributed across enemies in their stored order, with excess damage
carrying to the next enemy. Defeated enemies do not retaliate. Surviving enemies
act in order: Strike deals base attack, Charge doubles the next Strike, and
Debuff subtracts one attack next round. Shields absorb Strike damage across all
enemies and expire after the round. HP cannot fall below zero. AP refreshes each
round. There is no randomness in round evaluation. Default intent is Strike.
Won or defeated encounters reject further rounds until replaced by encounter
setup. Encounter creation and selection are later-phase integration work.

The shared HTTP/native completion service saves the calculated round inside the
existing prepared resolution before writing the task checkbox. It applies the
encounter and card transition in the same atomic battle-state commit. Recovery
reuses that saved calculation, including after a process restart. Another round
is blocked while a resolution is pending. Cancellation never evaluates a round.
Without an encounter, existing task completion behavior is preserved. Tactical
defeat does not undo a completed real-world task or its XP.

The shared state endpoint returns normalized card stats, the encounter's next
intents, and the last committed round. Combat Theater displays this data when an
encounter exists. Desktop state reads use the Python combat bridge, like writes.

Verification uses temporary synthetic Vaults:

```powershell
python -m pytest backend/tests/test_combat_tactics.py backend/tests/test_combat_completion.py backend/tests/test_combat_workflow.py -q
```
