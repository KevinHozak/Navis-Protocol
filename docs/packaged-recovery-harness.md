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
the exact isolated EXE, WebViews with a `--user-data-dir` inside the exact profile,
the configured Python running a script inside the copied backend, and
creation-time-compatible descendants. Sibling paths and incidental mentions of
the run path do not establish ownership.
If residual processes remain, launch refuses to proceed. Shutdown timeouts retain
evidence and processes for inspection; they do not trigger forceful cleanup.

## Results and timing

`recovery.json` contains monotonic elapsed seconds for observed host exit and
the first observed zero-owned-process sample, timestamped process samples,
explicit UI outcomes/history, EXE hash, and original-file integrity differences.
These timings include process-query overhead and are observation upper bounds,
not exact OS exit timestamps. The default polling deadline is 45 seconds
(`-ShutdownTimeoutSeconds` accepts 5–120); a slow CIM query can exceed it.

`report` requires correctly ordered launch/close events, zero current owned
processes and all three named UI checks passed with nonempty evidence for the
latest launch. Forced mode requires a running host to be terminated and the
recovered launch then normally closed. Two launches before a termination do not
constitute recovery; normal mode cannot include termination. Missing, stale,
pending or interrupted checks yield `incomplete`. A current failed UI check
overrides another pending check, and a timed-out shutdown remains `failed` even
with residual processes. Read the JSON result; report output does
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

## Offline regressions

```powershell
pwsh -NoProfile -File scripts/test-packaged-recovery-policy.ps1
```

The 43-case suite imports the same pure policy module as the harness. It tests
stale/reused PIDs, exact host identity, unrelated processes, sibling paths,
quoted paths with spaces, creation-time ancestry, incomplete/interrupted UI,
failure precedence and forced-run ordering. Five cases call the actual harness
entry point using mocked CIM snapshots and synthetic temporary JSON. Process
handle access, process-launch commands and network commands are blocked by
throwing stubs. The suite never runs the launch branch or loads a packaged EXE,
accesses the personal Vault, invokes UI automation or calls a provider. It needs
PowerShell 7 on Windows, without app dependencies, Pester or elevated CIM access.

These regressions reproduced and repaired overly broad substring ownership,
missing/stale UI checks passing, invalid recovery ordering passing, and failures
being hidden by pending work. No live-run verification is claimed for these
policy changes; the earlier packaged validations above describe their original
run conditions.

### Windows CI

`.github/workflows/recovery-offline.yml` runs this same offline command on
`windows-latest` for pushes and pull requests touching the harness, shared
policy, suite, recovery documentation or workflow. It also supports manual
dispatch. The job has a five-minute timeout and read-only repository permission.
Checkout does not persist credentials and includes only the offline test and
workflow-validation scripts plus the recovery workflow. No app build, app
dependency installation, Navis launch, UI automation, personal Vault mount or
provider request is part of the job.
Provider keys/config are explicitly empty and `NAVIS_ROOT` points to an unused
runner-temporary location. Tests use synthetic process records and their own
temporary JSON. A thrown assertion fails the CI step.

The initial offline suite passed in hosted Windows CI in
[PR #54](https://github.com/KevinHozak/Navis-Protocol/pull/54), merged at `8299c4c`.
The first workflow attempt failed validation before a Windows job started; moving
the runner-temporary path to step-level `env` resolved it. All 43 cases passed on
corrected published head `1de8ee7` in the
[Windows push run](https://github.com/KevinHozak/Navis-Protocol/actions/runs/42385402257)
and the [PR test-merge run](https://github.com/KevinHozak/Navis-Protocol/actions/runs/42385405738).

The semantic validation extension merged in
[PR #55](https://github.com/KevinHozak/Navis-Protocol/pull/55) at `acd603a`.
Its [Windows push run](https://github.com/KevinHozak/Navis-Protocol/actions/runs/42386550110)
checked out exact published head `6828cc7051a8411bca34bd4ef3e0181109715f38` and
passed actionlint semantic/rejection checks, all 9 pre-push checks and all 43
recovery policy cases. The [PR test-merge run](https://github.com/KevinHozak/Navis-Protocol/actions/runs/42386576491)
also passed those three groups. Secret scans passed on the same head. These
results qualify the stated workflow/policy scope, not a new packaged UI run or
the current application generally. No Navis launches, personal Vault access or
provider calls were made during CI; tool provisioning downloads are separate
from offline validation. No tests were rerun for the November 7 status update.

### Semantic validation before publication

Actionlint 1.7.7 performs workflow-schema and expression-context checks, including
rejecting `runner.temp` at job-level `env`. Plain YAML parsing is insufficient.
The pre-push hook checks changed recovery paths and runs the semantic checker
before the existing secret scan. It lints each affected pushed commit's workflow
from Git, not a potentially different working-tree copy. Invalid ref records or unavailable Git range
inspection fail closed. New branches or unavailable remote commit objects use
a conservative tree listing; ref deletions and unrelated updates skip this check.
This gate does not publish, launch applications, execute workflow commands, or
download tools. A missing actionlint executable blocks an affected push.

Explicit Windows x64 installation (tool provisioning uses the public release
endpoint; validation itself is offline):

```powershell
pwsh -NoProfile -File scripts/install-actionlint.ps1
# Or install from an already downloaded archive without any network access:
pwsh -NoProfile -File scripts/install-actionlint.ps1 -ArchivePath C:\Downloads\actionlint_1.7.7_windows_amd64.zip
```

The installer requires SHA-256
`7f12f1801bca3d480d67aaf7774f4c2a6359a3ca8eebe382c95c10c9704aa731`
before extracting the official archive into ignored `.tools/actionlint`.
The CI job provisions this same checksum-pinned tool before running semantic
validation and the 43 offline policy cases; it does not install app dependencies.

```powershell
pwsh -NoProfile -NonInteractive -File scripts/check-recovery-workflow.ps1
pwsh -NoProfile -NonInteractive -File scripts/test-recovery-workflow-lint.ps1
node scripts/test-recovery-workflow-push.mjs
```

For another local installation, supply `-ActionlintPath` or `ACTIONLINT_BIN` to
the checker; the semantic regression script accepts `-ActionlintPath` too.
ShellCheck and Pyflakes integrations are disabled, keeping validation within
actionlint. The regression script checks the real workflow, rejects a temporary
invalid job-level runner-context fixture, verifies nonzero-error propagation,
and rejects a missing tool. Nine offline Node assertions cover pre-push path
selection, new/deleted refs, multiple refs and fail-closed input/inspection errors.
All passed locally on 2026-11-07 using the verified actionlint 1.7.7 binary.
