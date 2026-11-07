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
