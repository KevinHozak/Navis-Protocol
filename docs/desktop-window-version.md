# Desktop window version (#246)

The native startup sets each initial webview window title to `Navis Protocol v`
plus the running Tauri package version. The title does not depend on the Vault,
HTTP backend or a frontend request. The healthy IPC indicator now reads only
`IPC online`; unavailable and Vault diagnostic messages retain their behavior.
Diagnostic APIs still return version metadata for troubleshooting.

## Verification - 2026-11-03

- Release executable and NSIS installer built as 1.11.38. Executable FileVersion
  and ProductVersion both report 1.11.38; synchronized manifests/lockfiles match.
- Full frontend suite and lint passed (existing lint warnings retained).
- 81 native library tests passed serially after packaging. An earlier test run
  overlapped frontend export replacement and failed on missing embedded assets;
  rerunning after the export completed passed without source changes.
- Two fresh isolated Vault/profile fixtures used identical copied release bytes,
  SHA-256 `3aed0062aedabeb8428391c67d30e9a85ed2f96a5af0044c19be93a3dc1bfa2c`.
  All 51 packaged Python resources matched source in each copy.
- Direct executable startup and the unchanged `Start_Navis_Desktop.bat` launcher
  both displayed the readable native title `Navis Protocol v1.11.38` and the
  lower-left `IPC online` indicator without version text. Screenshots and native
  accessibility/window readback confirmed the actual packaged UI.
- All six original files in each synthetic Vault stayed byte-identical. Only
  deterministic weekly Holocron HTML/JSON and manifest caches were added.
  Both app windows and their owned WebView processes were closed after checking.

Fixture launch environments explicitly selected the disabled OpenRouter route
and removed cloud key/config variables. No inference call or personal-Vault access
was required. Cloud generation remains disabled. This is not a clean-machine
installation test or a debug/dev-window verification.

Source review found no actionable issue in version authority, IPC diagnostics,
startup error propagation or the scoped diff. Independent external review was not
provided; it is separate from the recorded implementation/runtime checks.

## Delivered closeout — 2026-11-03

[PR #44](https://github.com/KevinHozak/Navis-Protocol/pull/44) merged at
`7edf1ffa15f23f06cc2cc8ba08cb5a297bae6a36` and
[#246](https://github.com/KevinHozak/Navis-Protocol-Private/issues/246) is closed
with all four acceptance criteria checked against the above evidence. The direct
and launcher checks are passing build-host evidence; clean-machine installation
and debug/dev-window behavior remain unclaimed. Cloud generation remains disabled.
