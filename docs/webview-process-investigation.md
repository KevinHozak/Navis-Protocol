# Packaged WebView process investigation

Investigation date: 2026-11-06 (America/Chicago).

## Result

No packaged Navis process accumulation reproduced in eight sequential
launch/close cycles. No application code or release version was changed.
The earlier roster-test failure remains unexplained; these measurements do not
establish that its cause was fixed or that longer sessions cannot reproduce it.

## Isolation and method

- Tested release 1.11.45, SHA-256
  `f24254c3c403bd9f4d7c5355b6e21255c54fb3c6e6277c758aff7ddee3cf352e`.
- Copied the prior synthetic roster Vault and packaged EXE/backend resources
  into `.tools/webview-lifetime-20261106`; never launched against the personal
  Vault. No backend HTTP service or dev server was needed.
- Set `NAVIS_ROOT`, `NAVIS_PYTHON`, and `WEBVIEW2_USER_DATA_FOLDER` explicitly.
  Selected `NAVIS_AI_PROVIDER=openrouter` with `OPENROUTER_API_KEY` and
  `NAVIS_OPENROUTER_CONFIG` removed. Also removed inherited Google/Gemini keys.
  No generation, sync, rollover, or health-write action was invoked.
- Recorded process IDs, parent IDs, creation times, executable paths and
  command lines through CIM. Ownership required the exact copied EXE path or
  a WebView command line containing the isolated profile path.
- Waited eight seconds after launch, requested normal main-window close with
  `Process.CloseMainWindow()`, allowed ten seconds for app exit and another
  five seconds before recording residual processes. No broad kill or cleanup
  command was used.

## Observations

| Scenario | Cycles | App / WebView while open | App / WebView after close |
| --- | ---: | --- | --- |
| Independent profiles | 3 | 1 / 6 each | 0 / 0 each |
| Same isolated profile reused | 3 | 1 / 6 each | 0 / 0 each |
| Copied profile from earlier failed roster fixture | 2 | 1 / 6 each | 0 / 0 each |

The last two cycles included forty additional seconds open for helper checks.
Installed WebView runtime: 157.0.4341.42. Its six processes comprised browser,
crash handler, GPU, network utility, storage utility and renderer processes.
An initial measurement-script output bug incorrectly flagged an empty process
list as residuals; its saved observation contained zero processes. The script
was corrected before the six-cycle baseline above.

The computer-use helper returned window listings and an accessibility tree
showing Dashboard read completion and IPC online. A Party click failed with
`coordinate input geometry is unavailable`; a later activation failed with
`foreground window did not report a process id`. Screenshot capture did not
reliably show the target. No successful navigation is claimed. These failures
did not reproduce the earlier list-window timeouts or process accumulation.

Synthetic-Vault integrity checks identified two changed existing files:
`Bridge/Holocron/weekly_manifest.json` and
`Bridge/Holocron/Weekly/2026-W45.json`, local startup/read synthesis outputs.
This was not a byte-preserving launch. No personal Vault files were used.

## Evidence and limits

Ignored local evidence and harness:

- `.tools/webview-lifetime.ps1`
- `.tools/webview-lifetime-20261106/observations.json` (six-cycle baseline)
- `.tools/webview-lifetime-20261106/helper-observations.json`
- `.tools/webview-lifetime-20261106/integrity.json`
- `.tools/webview-lifetime-20261106/helper-integrity.json`

This covers sequential normal shutdown, fresh/reused profiles, and a copy of
the previously problematic profile. It does not reproduce the exact previous
desktop/runtime state, simultaneous app instances, forced termination,
long-running navigation, or a stalled helper. If buildup recurs, capture
process ownership and creation times before cleanup and preserve the triggering
launch/close sequence. A code fix requires a repeatable failing case.

## Forced-close follow-up

On 2026-11-06 (America/Chicago), tested three additional independent synthetic
Vaults and fresh profiles. In each cycle, launched the same release, forcibly
terminated only the host process, and relaunched with that cycle's same profile
and Vault. Before termination, verified the exact copied EXE path, PID and
creation timestamp. Used `Process.Kill()` without killing the process tree so
WebView child lifetimes remained observable. All launches used the same
cloud-disabled environment described above.

| Cycle | Initial WebViews | After host termination: successive samples | After relaunch | After normal close |
| --- | ---: | --- | ---: | --- |
| 1 | 6 | 3, 2, 1 | 6 | 0 at five-second check |
| 2 | 6 | 6, 5, 0 | 6 | 5 at five-second check; 0 at later inspection |
| 3 | 6 | 6, 6, 2 | 6 | 0 at five-second check |

Post-termination samples followed successive waits of one, two and five
seconds, plus CIM query overhead; these are not exact elapsed-time samples.
The last survivor in cycle 1 was a crashpad handler. No manual WebView process
termination was needed. Cycle 2's late inspection found no remaining processes
before cycle 3 started; its exact exit time was not captured. A final CIM check
found zero owned app, WebView or Python processes across all three fixtures.

All three relaunched windows exposed `Dashboard: Read complete` through the
computer-use accessibility API. Cycles 2 and 3 also exposed System HUD content.
Cycle 1 still exposed `UPLINK SYNCHRONIZING` and mounting text on a repeated
read despite dashboard read completion. Because these were hidden-window
checks, no complete visual-recovery pass is claimed for cycle 1. The observation
did not recur in cycles 2 and 3 and was not established as an application defect.

The PID guard initially rejected a timestamp comparison because JSON parsing
converted the saved ISO timestamp into a date object. It refused termination;
the harness was corrected to compare UTC ticks before proceeding. This was a
test-harness correction, not a product change.

Each Vault retained 14 of its 17 original files byte-for-byte. The changed
originals were the weekly Holocron manifest, JSON and HTML startup/read synthesis
outputs. No personal Vault, sync, rollover or generation action was used.

Evidence remains ignored locally under `.tools/webview-forced-close-20261106/`:
per-cycle process snapshots, process identity records, initial hashes and
`final-integrity.json`, plus the final empty `final-processes.json`. The harness
is `.tools/webview-forced-close.ps1`. Early empty snapshots were emitted through
an empty PowerShell pipeline and did not create JSON files; their zero counts
are retained in execution output. The harness now serializes empty arrays
explicitly. Accessibility observations are retained in the chat tool results.

No persistent accumulation or reproducible Navis defect was established, so no
application fix or version bump was made. Forced termination can leave transient
WebView processes, and five seconds is not a reliable universal shutdown bound.
These three cycles do not establish behavior during sustained overlapping
instances, long sessions, or a stalled helper.

## Visible UI recovery follow-up

On 2026-11-07 (America/Chicago), ran three new isolated forced-close/relaunch
cycles against release 1.11.45 with the same EXE hash. Each had its own copied
synthetic Vault and fresh profile under `.tools/webview-visible-20261107/`.
The harness `.tools/webview-visible.ps1` used normal visible windows instead of
hidden windows; the computer-use helper activated each recovered window and
captured its rendered content. Cloud generation remained disabled and
unconfigured using the environment isolation above.

| Cycle | Recovered System HUD | Party navigation | Combat navigation |
| --- | --- | --- | --- |
| 1 | Loaded | Banter Feed loaded | Battle Field and encounter controls loaded; loader cleared |
| 2 | Loaded | Banter Feed loaded | Battle Field loaded; encounter choices still loading when closed; later normal-launch recheck passed |
| 3 | Loaded | Banter Feed loaded | Battle Field and encounter controls loaded; loader cleared |

Cycle 2 was closed before its encounter-choice request was observed completing,
so it is not a complete post-crash encounter-loading acceptance pass. Reopened
its existing isolated profile normally (without another forced termination),
navigated directly to Combat and observed the loader clear on a later capture
after an additional fifteen-second wait. This confirms the profile could load
Combat, but does not retroactively certify the interrupted observation.

Transient fade transitions were observed and settled on repeated captures.
No persistent `UPLINK SYNCHRONIZING` or mounting state reproduced in these
visible checks. Party's empty Banter Feed correctly requested at least two
squad members; no Resonate, encounter preview/start, combat resolution, sync,
rollover or generation action was invoked. The synthetic Keeper portrait used
the explicit `IMAGE UNAVAILABLE` fallback in Battle Field.

The helper sometimes returned a 16-by-16 icon capture before the main window
capture. An input attempt against that icon failed its bounds check; after
refreshing, inputs used the observed full-window screenshot. This was tooling
geometry, not evidence of a Navis navigation failure. Cycle 2 process queries
also took longer to return; no startup-duration guarantee is inferred.

Post-relaunch WebView counts were 5, 7 and 7 at the respective snapshots;
cycle 2's additional normal launch had 6. All normal closes completed with
zero owned processes at the final checks. A final cross-fixture CIM snapshot
also found zero app, WebView or Python processes. The three Holocron synthesis
outputs and `Battle/.completion.lock` changed in each synthetic Vault; the
other 13 original files remained byte-identical. No personal Vault was used.

Process snapshots, identity guards and integrity results remain ignored in
the fixture directory; screenshots and UI observations are in this chat's
computer-use tool results. No reproducible application defect was established,
so no application code, release version or packaged binary was changed.

## Reusable harness

The tracked [packaged recovery harness](packaged-recovery-harness.md) replaces
the historical fixture dependencies for future runs. It creates a literal
synthetic Vault, records stopwatch-based shutdown samples and explicit UI
outcomes/history, and keeps provider credentials/configuration out of its child
environment. One normal-close and one forced-close/relaunch validation passed
on 2026-11-07, including System HUD, Party and settled Combat navigation. Both
ended with zero owned processes and no changed original synthetic Vault files.
No application binary, app source or version was changed for this harness work.
