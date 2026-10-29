# Biometrics sync

The Navis backend and native desktop bundle run the maintained helper at
`backend/scripts/sync_biometrics.py`. The previous helper lived in the local
Agents scripts directory; only source and mocked tests moved into this
repository. The Tauri resource list includes the helper, not OAuth credentials
or token data.

## Authorization

OAuth client configuration and the dedicated biometrics token stay outside the
repository. By default, the helper reads
`C:\Projects\Agents\credentials.json` and
`C:\Projects\Agents\biometrics_token.json`. Set
`NAVIS_BIOMETRICS_CLIENT_SECRETS_FILE` or `NAVIS_BIOMETRICS_TOKEN_FILE` to use
different local paths. The Gmail-shared `token.json` is not used.

To refresh Health authorization without importing data, run from the repository
root:

```powershell
& .\backend\.venv\Scripts\python.exe backend\scripts\sync_biometrics.py --reauthorize-only
```

This opens a bounded local authorization callback on loopback, requests fresh
offline credentials for the existing Health scopes, and replaces the dedicated
token only after receiving valid credentials with every required scope and a
refresh token. Cancellation or failure leaves the previous token in place.
This mode does not call `import_data`, query the Health API, or access SQLite or
rollover. The normal command with no options retains its import behavior.

## Vault output

The final database is written to
`%NAVIS_ROOT%\Keeper\FitbitChronicle.db`; when `NAVIS_ROOT` is unset, the
established `G:\My Drive\Navis-Vault` default is used. Native sync passes its
configured Vault root to the helper. Fitbit export inputs retain their existing
external paths.

`NAVIS_BIOMETRICS_SCRIPT` can point the backend sync engine at an explicit local
helper path for development or support. The default resolves the helper beside
the backend source or bundled backend resources.
