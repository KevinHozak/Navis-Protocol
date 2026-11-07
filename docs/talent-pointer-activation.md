# Talent pointer activation repair — 2026-11-05

**Result: passed in fresh web and packaged 1.11.44 fixtures.** This resolves the
pointer observation from the [original talent lifecycle smoke](talent-allocation-lifecycle-smoke.md).

## Confirmed defects

A fresh baseline on merged main `33b489a` reproduced the failure. Clicking the
visible Deep Work Flow circle opened its details but left rank zero unchanged.
Rendered DOM hit testing at the circle center returned the detail paragraph,
not the SVG circle: the circle occupied x=450.70–485.06 / y=402.26–436.62, while
the detail panel occupied x=354–802 / y=336–518. Hover inserted that panel over
the target before the click could reach it.

Separately, the decorative `animate-ping` transform scaled around the SVG origin.
One recorded main circle was at x=450.70 / y=353.26 with size 34.37, while the
glow had drifted to x=548.59 / y=560.15 with size 83.83. The enlarged group center
could consequently miss the visible circle when addressed as an accessible
button. The earlier automation limitation therefore concealed a real layout and
hit-target defect; allocation service behavior was not the cause.

The repair moves the interactive detail panel into normal flow below the graph.
It retains the existing description, prerequisites and Inscribe action. Decorative
glow/spinner transforms now use their own fill boxes and centered origins, and
do not receive pointer events. Keyboard controls, allocation guards and backend
semantics are unchanged.

## Fresh verification

Both fixtures began with separate synthetic Vaults, level 3 / 3,000 seeded XP,
three available points and no allocations. Allocation mutations used the UI.

| Scenario | Web | Packaged desktop |
| --- | --- | --- |
| Direct pointer allocation | Click Deep Work Flow once → rank 1, 2 points, Clarity unlocked | Direct mouse click at the observed circle → same result |
| Switching nodes with details open | Click Clarity twice → rank 2, mastered, 0 points | Same, through native node pointer targets |
| Keyboard/exhaustion | Arrow Down selected Deep Work Flow; Enter at 0 points added nothing | Down selected Deep Work Flow; Space at 0 points added nothing |
| Persistence | Reload and reopen XP Manifold retained both ranks and 0 points | Graceful exit, zero old fixture processes, same-profile relaunch retained both ranks and 0 points |
| Combat effect after persistence | UI setup/binding/Execute loaded Clarity rank 2; 20% shield bonus; 12 absorbed; 0 damage; HP 100 / turn 2 | Same |
| Durable integrity | One round, one 12-XP task award, no extra allocations; correct card piles and completed task | Same |

At **1024×768, 1280×720 and 1600×900**, rendered web details started below the
graph. Packaged pointer clicks succeeded with the detail panel present, and
decorative glow stayed around its node. Screenshots and DOM geometry receipts
are retained privately. The web source was 1.11.44; its unused fixture EXE copy
was still 1.11.43 because web checks began during native compilation. The actual
desktop fixture was prepared after build completion from the verified 1.11.44
EXE and all 54 declared runtime resources.

Two navigation observations were retained separately: the baseline web roster
needed a reload, and one packaged combat roster remained synchronizing until
leaving/reopening its sector. No mutation was repeated to recover navigation.
Neither prevented the fresh allocation, persistence or perk checks, and this
repair does not claim to resolve all navigation-loading behavior.
The later [roster investigation and 1.11.45 repair](roster-loading-recovery.md)
reproduced a stale loader after completed entity requests and passed fresh
web/packaged switching and retry checks.

## Checks, build and cleanup

- Full frontend tests and lint passed (existing lint warnings).
- Desktop typecheck and **82 native unit tests plus one launcher test** passed.
- **17 backend talent/modifier tests** passed.
- Windows x64 release build passed; EXE and NSIS product versions are **1.11.44**.
  EXE SHA-256: `204dffda157cabb1ad844af7aed256d592f0aed46d97754a86a49dc84f474da6`.
- Each 13-file post-seed baseline changed only the progression DB, battle state,
  companion XP projection and target journal. Nine originals stayed byte-identical;
  journal BOM/CRLF and unrelated text were preserved.
- Baseline and repaired fixture processes were stopped, temporary browser tabs
  closed, viewport override reset, and ports 18171/18172 had no listeners.

Cloud generation stayed unconfigured and disabled. No personal Vault, live model
call, sync, rollover, installer execution or production migration was used. This
is scoped pointer/lifecycle acceptance, not broad human-usability certification.
