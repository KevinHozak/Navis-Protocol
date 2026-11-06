# Talent allocation lifecycle smoke — 2026-11-05

**Original 1.11.43 core lifecycle: passed.** Fresh isolated web and packaged desktop fixtures
verified talent allocation, prerequisite unlocking, refresh/relaunch persistence
and one deterministic combat perk. Direct pointer activation of SVG nodes remains
inconclusive under automation in this original run; it was not a pointer-usability
pass. The later [1.11.44 pointer repair and fresh rerun](talent-pointer-activation.md)
confirmed and fixed the cause, then passed pointer allocation in both runtimes.

## Source, runtime and isolation

- Merged main: `33b489a2f00cbabfe48f0a1fda28c2bdb38b755d` (PR #50).
- Existing packaged Windows x64 release: **1.11.43**; no application changes or
  rebuild were needed. EXE SHA-256:
  `95052a93ae7aa879c96fa33826da5d9ae6be8e13ca9dde9ad059df890cd6a873`.
- Separate new synthetic Vaults and desktop WebView profile. The packaged fixture
  copied the EXE and 54 declared runtime resources, checked against source.
- Web used loopback ports 18171/18172 with lifespan/background startup disabled.
  Desktop used its native routes and packaged Python bridge, with web servers
  stopped. No personal Vault or live integration was accessed.
- OpenRouter remained unconfigured, generation disabled, and provider secrets
  removed from fixture process environments. No model calls were made.

Each fixture started at level 3 with one explicitly seeded 3,000-XP synthetic
ledger award, three talent points and no allocations. Seed setup was fixture
preparation, not a tested application award flow. All tested talent allocations,
encounter preview/confirmation, card binding and Execute actions used the UI.

## Allocation and persistence

| Check | Web | Packaged desktop |
| --- | --- | --- |
| Initial state | Deep Work Flow available; Mindful Clarity locked; 3 points | Same |
| Prerequisite allocation | Enter allocated Deep Work Flow rank 1; 2 points; Clarity unlocked | Tab/Enter allocated rank 1; Clarity unlocked |
| Dependent perk | Arrow Up focused Clarity; Space allocated rank 1; Enter allocated rank 2 | Up focused Clarity; Space allocated rank 1; tooltip Inscribe button allocated rank 2 |
| Final state | Deep Work Flow 1/3, Clarity 2/2 mastered, 3 ranks spent, 0 points | Same |
| Exhaustion guards | Enter on mastered Clarity and zero-point Deep Work Flow did not add ranks; Points Needed / disabled action shown | Mastered and insufficient-points states rendered; no additional guard activation claimed |
| Persistence | Reload, return to Command → Party → XP Manifold: same ranks and points | Graceful close, complete process exit, same-profile relaunch and return to XP Manifold: same ranks and points |

SQLite reads confirmed exactly two allocation rows, with ranks 1 and 2, after
allocation, refresh/relaunch, combat and shutdown. No allocation was seeded or
replaced to obtain this result. No extra XP was needed after the initial seed.

### Pointer interaction limit

The browser accessibility activation API rejected SVG activation. Locator clicks
on the selected SVG node did not visibly allocate, while Enter/Space did. Native
element and circle clicks similarly did not allocate in the observed attempts;
keyboard navigation and the tooltip's actual Inscribe button worked. The tooltip
overlays part of the graph, and SVG hit targeting may be relevant, but this run
did not isolate the cause. This is an unresolved interaction observation, not a
confirmed allocation-service defect or proof that ordinary human clicks fail.
A focused pointer hit-target/tooltip reproduction is the next bounded check if
further interaction acceptance is wanted. No source repair was made in this smoke.

## Combat perk effect

The selected perk was **Mindful Clarity rank 2**, represented by
`focus_stamina_boost: 2`. Its combat modifier adds **20% shield**. Both fixtures
had no squad synergies, a zero-attack top card, a 10-shield guard card, and a
100-HP Sentinel with a deterministic 12-damage Strike. The opponent stayed alive
so incoming damage was actually evaluated.

Before allocation, a read-only shared evaluator control on the identical card
and encounter inputs, with no talent perks, absorbed **10** and dealt **2** player
damage (HP 98). This was an evaluator control, not a second UI-operated fight.

After persisted allocation, each runtime performed reviewed encounter setup,
bound Repair telescope to the card pair and executed one real completion. The
durable completion record in both runtimes showed:

- Loaded perks: Deep Work Flow 1 and Mindful Clarity 2.
- Shield modifier **20%**, shield absorbed **12**, player damage **0**.
- Encounter advanced from turn 1 to **turn 2**, Keeper HP **100**, enemy HP 100.
- Completion phase `complete`; one recorded combat round; cards a/b discarded
  once, c/d retained, and the active task binding removed.
- Ledger: the original synthetic 3,000 XP plus one **12-XP** task award. Talent
  ranks and zero-point balance remained unchanged.

The rendered Battle Field showed turn 2 / HP 100 in both runtimes. Only this
shield perk and round were qualified; other perks, win/defeat outcomes, sound
perception and broad accessibility/usability are not certified by this smoke.

## Integrity, cleanup and retained evidence

Each post-seed baseline contained 13 files. Only the progression database, battle
state, companion XP projection and target journal changed; the other nine
original files remained byte-identical. The journal retained BOM/CRLF and its
unrelated snowman text. Only Repair telescope was completed, with supported task
completion metadata; Test beacon stayed unchecked.

The temporary browser tab was closed. Both applications, server children and
WebView processes were stopped. Final checks found **zero fixture processes and
zero listeners** on 18171/18172. Private JSON receipts, baseline hashes, control
results and screenshots are retained outside the tracked delivery. No sync,
rollover, installation, personal-data migration, commit or publication occurred.

These results add scoped runtime evidence to the existing talent records. They
do not reopen the explicitly waived XP-dashboard acceptance or imply production
Vault adoption.
