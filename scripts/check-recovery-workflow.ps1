#requires -Version 7.0
[CmdletBinding()]
param(
  [string]$ActionlintPath=$env:ACTIONLINT_BIN,
  [string]$WorkflowPath=(Join-Path $PSScriptRoot '../.github/workflows/recovery-offline.yml')
)
$ErrorActionPreference='Stop'
if (!$ActionlintPath) {
  $local=Join-Path $PSScriptRoot '../.tools/actionlint/actionlint.exe'
  if (Test-Path -LiteralPath $local -PathType Leaf) { $ActionlintPath=$local }
  else {
    $command=Get-Command actionlint -CommandType Application -ErrorAction SilentlyContinue
    if ($command) { $ActionlintPath=$command.Source }
  }
}
if (!$ActionlintPath -or !(Test-Path -LiteralPath $ActionlintPath -PathType Leaf)) {
  throw 'Actionlint is required. Supply -ActionlintPath or ACTIONLINT_BIN. This checker never downloads tools or substitutes YAML parsing for semantic validation.'
}
$workflow=(Resolve-Path -LiteralPath $WorkflowPath).Path
# Disable optional external analyzers; actionlint itself performs workflow and
# expression-context checks without executing workflow commands or using network.
& $ActionlintPath '-shellcheck=' '-pyflakes=' $workflow
if ($LASTEXITCODE -ne 0) { throw "Actionlint semantic validation failed (exit $LASTEXITCODE)." }
Write-Output 'Recovery workflow semantic validation passed.'
