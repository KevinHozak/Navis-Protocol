#requires -Version 7.0
[CmdletBinding()]
param([string]$ActionlintPath=(Join-Path $PSScriptRoot '../.tools/actionlint/actionlint.exe'))
$ErrorActionPreference='Stop'
$checker=Join-Path $PSScriptRoot 'check-recovery-workflow.ps1'
& $checker -ActionlintPath $ActionlintPath
$fixture=Join-Path ([IO.Path]::GetTempPath()) ('navis-invalid-workflow-'+[guid]::NewGuid()+'.yml')
try {
  # Reproduce the exact class of semantic error missed by a YAML parser.
  @'
name: Invalid runner context fixture
on: push
jobs:
  regression:
    runs-on: windows-latest
    env:
      NAVIS_ROOT: ${{ runner.temp }}/unused
    steps:
      - run: echo static-fixture
'@ | Set-Content -LiteralPath $fixture -Encoding utf8
  $output=@(& $ActionlintPath '-shellcheck=' '-pyflakes=' $fixture 2>&1)
  if ($LASTEXITCODE -eq 0 -or ($output -join "`n") -notmatch 'runner') { throw 'Actionlint did not reject the invalid runner context fixture.' }
  $rejected=$false
  try { & $checker -ActionlintPath $ActionlintPath -WorkflowPath $fixture | Out-Null } catch {
    if ($_.Exception.Message -notlike 'Actionlint semantic validation failed*') { throw }
    $rejected=$true
  }
  if (!$rejected) { throw 'Checker did not propagate the actionlint failure.' }
  $missingRejected=$false
  try { & $checker -ActionlintPath ($fixture+'.missing') | Out-Null } catch {
    if ($_.Exception.Message -notlike 'Actionlint is required*') { throw }
    $missingRejected=$true
  }
  if (!$missingRejected) { throw 'Checker accepted a missing actionlint executable.' }
  Write-Output 'Semantic workflow checks passed: real workflow accepted, invalid runner context rejected, nonzero status propagated, missing tool rejected.'
} finally {
  if (Test-Path -LiteralPath $fixture) { Remove-Item -LiteralPath $fixture }
}
