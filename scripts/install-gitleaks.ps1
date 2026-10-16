$ErrorActionPreference = 'Stop'
$version = '8.30.1'
$expectedHash = 'd29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e'
$repoRoot = Split-Path -Parent $PSScriptRoot
$destination = Join-Path $repoRoot '.tools\gitleaks'
$archive = Join-Path ([IO.Path]::GetTempPath()) ("navis-gitleaks-" + [guid]::NewGuid().ToString() + '.zip')
try {
    Invoke-WebRequest -Uri "https://github.com/gitleaks/gitleaks/releases/download/v$version/gitleaks_${version}_windows_x64.zip" -OutFile $archive
    $actualHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash
    if ($actualHash -ne $expectedHash) {
        throw 'Gitleaks archive checksum mismatch; refusing to install.'
    }
    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    Expand-Archive -LiteralPath $archive -DestinationPath $destination -Force
    & (Join-Path $destination 'gitleaks.exe') version
    if ($LASTEXITCODE -ne 0) { throw 'Gitleaks installation verification failed.' }
} finally {
    if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive }
}
