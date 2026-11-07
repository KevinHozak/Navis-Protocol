# Packaged recovery harness

Run `scripts/test-packaged-recovery.ps1` with PowerShell 7 on Windows. It
requires CIM process access, an existing packaged release with its bundled
resources, and an installed Python runtime with the backend dependencies.
It does not build, install, commit, or publish anything.

The harness generates a small synthetic Vault from literals, copies only the
EXE and resources declared in `tauri.conf.json`, and uses a separate WebView
profile. No old `.tools` fixture is an input. Defaults are the current release
directory and `backend/.venv/Scripts/python.exe`; override with
`-ReleaseDirectory` and `-Python` at preparation time. The EXE hash is recorded.

Each run directory must be new. Preparation refuses an existing directory.
Use ignored local storage for profiles and evidence; it is never automatically
deleted. No personal Vault files are read or copied. The child environment is
cleared and rebuilt from Windows runtime paths plus explicit synthetic Vault,
profile and Python paths. `NAVIS_AI_PROVIDER=openrouter` is set with no provider
credentials or config. Do not invoke generation, sync, rollover or combat writes
while performing the navigation checks.

## Normal close

From the repository root:

```powershell
$run = '.tools/recovery-example-normal'
./scripts/test-packaged-recovery.ps1 -Action prepare -RunDirectory $run -Mode normal
./scripts/test-packaged-recovery.ps1 -Action launch -RunDirectory $run
```

Observe the visible System HUD, Party Banter Feed and Combat Battle Field using
the installed computer-use skill or manually. Wait for transitions and encounter
loading to settle. Record each observed check separately:

```powershell
./scripts/test-packaged-recovery.ps1 -Action ui -RunDirectory $run `
  -Check SystemHUD -Outcome passed -Evidence 'Describe the observed content and evidence location'
# Repeat for -Check Party and -Check Combat using their actual observations.
./scripts/test-packaged-recovery.ps1 -Action close -RunDirectory $run
./scripts/test-packaged-recovery.ps1 -Action report -RunDirectory $run
```

`ui` records observations; it does not automate or infer them. Outcomes are
`passed`, `failed`, or `interrupted`; unobserved checks remain `pending`. If a
capture fails, loading is still in progress when testing stops, or a window is
closed before verification, record `interrupted` with the reason. Do not turn
elapsed time or a live process into a UI pass. History preserves replaced
outcomes and earlier-launch checks. Every launch resets the current UI checks.

## Forced close and recovery

Prepare a separate new directory with `-Mode forced`, then run:

```powershell
./scripts/test-packaged-recovery.ps1 -Action launch -RunDirectory $run
# Allow initial startup; then terminate only this validated fixture host.
./scripts/test-packaged-recovery.ps1 -Action terminate -RunDirectory $run
./scripts/test-packaged-recovery.ps1 -Action launch -RunDirectory $run
# Observe and record all three UI checks on this recovered launch.
./scripts/test-packaged-recovery.ps1 -Action close -RunDirectory $run
./scripts/test-packaged-recovery.ps1 -Action report -RunDirectory $run
```

Terminate and close validate PID, EXE path and creation-time ticks before acting.
They never kill a process tree or use broad stop scripts. Process samples include
matching isolated EXE/profile commands and creation-time-compatible descendants.
If residual processes remain, launch refuses to proceed. Shutdown timeouts retain
evidence and processes for inspection; they do not trigger forceful cleanup.

## Results and timing

`recovery.json` contains monotonic elapsed seconds for observed host exit and
the first observed zero-owned-process sample, timestamped process samples,
explicit UI outcomes/history, EXE hash, and original-file integrity differences.
These timings include process-query overhead and are observation upper bounds,
not exact OS exit timestamps. The default polling deadline is 45 seconds
(`-ShutdownTimeoutSeconds` accepts 5–120); a slow CIM query can exceed it.

`report` requires a completed normal close, zero current owned processes and
all current-launch UI checks passed. Forced mode also requires termination and
at least two launches. Pending/interrupted checks yield `incomplete`, failed UI
or timed-out shutdown yields `failed`. Read the JSON result; report output does
not use a nonzero exit code merely for an incomplete result. Process/command
failures throw normally. Integrity differences are reported separately because
startup/read paths can generate local caches and lock files.

The synthetic Vault has no biometric/readiness/XP history or portrait assets;
unavailable values and image fallbacks are expected. Navigation checks do not
certify data-rich dashboards, generation quality or combat mutation correctness.

## Validation on 2026-11-07

Validated one normal-close run and one forced-close/relaunch run against the
existing release 1.11.45 (EXE SHA-256
`f24254c3c403bd9f4d7c5355b6e21255c54fb3c6e6277c758aff7ddee3cf352e`).
Both final reports passed with all three visible UI checks observed complete
and zero remaining processes. Pending/interrupted checks were also observed to
leave the report incomplete before the normal run finished. UI history retains
the replaced interrupted observation. No generation action was invoked.

| Action | Host exit observed (seconds) | All owned processes gone (seconds) |
| --- | ---: | ---: |
| Normal run: close | 1.808 | 3.686 |
| Forced run: terminate | 0.012 | 2.909 |
| Forced run: recovered close | 2.179 | 2.851 |

Both generated Vaults retained every original file byte-for-byte. Added files
were the battle completion lock and three local Holocron cache outputs. Private
local evidence is in `.tools/recovery-harness-20261107/{normal,forced}/recovery.json`;
UI screenshots are retained in the chat tool results. The console timing output
was adjusted to print the recorded sample time rather than including subsequent
JSON-save overhead. The table uses the recorded sample times.
