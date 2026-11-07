#requires -Version 7.0
# Explicit tool provisioning only. The validation scripts never download tools.
[CmdletBinding()]
param([string]$ArchivePath)
$ErrorActionPreference='Stop'
$version='1.7.7'
$expected='7f12f1801bca3d480d67aaf7774f4c2a6359a3ca8eebe382c95c10c9704aa731'
$destination=Join-Path $PSScriptRoot '../.tools/actionlint'
$temporary=$null
try {
  if (!$ArchivePath) {
    $temporary=Join-Path ([IO.Path]::GetTempPath()) ('navis-actionlint-'+[guid]::NewGuid()+'.zip')
    $ArchivePath=$temporary
    Invoke-WebRequest -Uri "https://github.com/rhysd/actionlint/releases/download/v$version/actionlint_${version}_windows_amd64.zip" -OutFile $ArchivePath
  }
  if ((Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash -ne $expected) { throw 'Actionlint archive checksum mismatch; refusing to extract.' }
  New-Item -ItemType Directory -Path $destination -Force | Out-Null
  Expand-Archive -LiteralPath $ArchivePath -DestinationPath $destination -Force
  & (Join-Path $destination 'actionlint.exe') -version
  if ($LASTEXITCODE -ne 0) { throw 'Actionlint installation verification failed.' }
} finally {
  if ($temporary -and (Test-Path -LiteralPath $temporary)) { Remove-Item -LiteralPath $temporary }
}
