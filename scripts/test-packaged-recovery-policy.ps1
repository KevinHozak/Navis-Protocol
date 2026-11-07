#requires -Version 7.0
$ErrorActionPreference='Stop'
# Fail immediately if this offline suite accidentally reaches live services.
function Get-CimInstance { throw 'Offline suite forbids live process queries' }
function Get-Process { throw 'Offline suite forbids live process access' }
function Start-Process { throw 'Offline suite forbids process launches' }
function Invoke-WebRequest { throw 'Offline suite forbids network requests' }
function Invoke-RestMethod { throw 'Offline suite forbids network requests' }
Import-Module (Join-Path $PSScriptRoot 'packaged-recovery-policy.psm1') -Force
$failures=[Collections.Generic.List[string]]::new(); $script:total=0
function Case([string]$Name, [scriptblock]$Body) {
  $script:total++
  try { & $Body; Write-Output "PASS $Name" } catch { $failures.Add("${Name}: $_"); Write-Output "FAIL $Name" }
}
function Equal($Actual,$Expected) { if ($Actual -cne $Expected) { throw "Expected '$Expected', got '$Actual'" } }
$root='C:\Synthetic Fixtures\run'; $exe="$root\release\navis-protocol.exe"
$fixture=@{run=$root;exe=$exe;profile="$root\profile";python='C:\Runtime\python.exe'}
$epoch=[datetime]'2026-11-07T10:00:00Z'
function ProcessRecord($Id,$Parent,$Name,$Path,$Command,$Seconds=0) {
  [pscustomobject]@{ProcessId=$Id;ParentProcessId=$Parent;Name=$Name;ExecutablePath=$Path;CommandLine=$Command;CreationDate=$epoch.AddSeconds($Seconds)}
}
$hostRecord=ProcessRecord 100 1 'navis-protocol.exe' $exe "`"$exe`""
$saved=@{pid=100;ticks=$epoch.ToUniversalTime().Ticks}
Case 'exact host identity accepted' { Equal (Test-RecoveryHostIdentity $hostRecord $saved $exe) $true }
Case 'exited/stale PID rejected' { Equal (Test-RecoveryHostIdentity $null $saved $exe) $false }
Case 'same path reused PID rejected' { Equal (Test-RecoveryHostIdentity (ProcessRecord 100 1 'navis-protocol.exe' $exe $exe 5) $saved $exe) $false }
Case 'different PID rejected' { Equal (Test-RecoveryHostIdentity (ProcessRecord 101 1 'navis-protocol.exe' $exe $exe) $saved $exe) $false }
Case 'different executable rejected' { Equal (Test-RecoveryHostIdentity (ProcessRecord 100 1 'other.exe' 'C:\Other\other.exe' '') $saved $exe) $false }
Case 'missing creation date rejected' { $p=$hostRecord.PSObject.Copy(); $p.CreationDate=$null; Equal (Test-RecoveryHostIdentity $p $saved $exe) $false }
Case 'empty snapshot remains empty' { $p=Get-RecoveryOwnedProcesses @() $fixture; Equal $p.Count 0 }
Case 'unrelated names and paths excluded' {
  $p=Get-RecoveryOwnedProcesses @((ProcessRecord 200 1 'navis-protocol.exe' 'C:\Other\navis-protocol.exe' ''),(ProcessRecord 201 1 'msedgewebview2.exe' 'C:\Runtime\msedgewebview2.exe' '--user-data-dir=C:\Other\profile')) $fixture
  Equal $p.Count 0
}
Case 'profile WebView and direct host selected' {
  $p=Get-RecoveryOwnedProcesses @($hostRecord,(ProcessRecord 201 100 'msedgewebview2.exe' 'C:\Runtime\msedgewebview2.exe' "--user-data-dir=`"$root\profile\EBWebView`"" 1)) $fixture
  Equal $p.Count 2
}
Case 'sibling profile substring excluded' {
  $p=Get-RecoveryOwnedProcesses @((ProcessRecord 201 1 'msedgewebview2.exe' 'C:\Runtime\msedgewebview2.exe' "--user-data-dir=`"$root-other\profile\EBWebView`"")) $fixture
  Equal $p.Count 0
}
Case 'incidental run mention excluded' {
  $p=Get-RecoveryOwnedProcesses @((ProcessRecord 201 1 'python.exe' 'C:\Runtime\python.exe' "other.py --note=`"$root`"")) $fixture
  Equal $p.Count 0
}
Case 'synthetic native Python helper selected' {
  $p=Get-RecoveryOwnedProcesses @((ProcessRecord 201 1 'python.exe' 'C:\Runtime\python.exe' "`"C:\Runtime\python.exe`" `"$root\release\backend\native_combat.py`"")) $fixture
  Equal $p.Count 1
}
Case 'creation-compatible descendants selected transitively' {
  $p=Get-RecoveryOwnedProcesses @($hostRecord,(ProcessRecord 201 100 'helper.exe' 'C:\Runtime\helper.exe' '' 1),(ProcessRecord 202 201 'child.exe' 'C:\Runtime\child.exe' '' 2)) $fixture
  Equal $p.Count 3
}
Case 'older child of reused parent PID excluded' {
  $p=Get-RecoveryOwnedProcesses @($hostRecord,(ProcessRecord 201 100 'helper.exe' 'C:\Runtime\helper.exe' '' -1)) $fixture
  Equal $p.Count 1
}
Case 'profile path traversal excluded' {
  $p=Get-RecoveryOwnedProcesses @((ProcessRecord 201 1 'msedgewebview2.exe' 'C:\Runtime\msedgewebview2.exe' "--user-data-dir=`"$root\profile\..\other`"")) $fixture
  Equal $p.Count 0
}
Case 'profile mentioned in unrelated option excluded' {
  $p=Get-RecoveryOwnedProcesses @((ProcessRecord 201 1 'msedgewebview2.exe' 'C:\Runtime\msedgewebview2.exe' "--note=`"$root\profile\EBWebView`"")) $fixture
  Equal $p.Count 0
}
Case 'sibling Python helper excluded' {
  $p=Get-RecoveryOwnedProcesses @((ProcessRecord 201 1 'python.exe' 'C:\Runtime\python.exe' "`"$root\release\backend-other\native_combat.py`"")) $fixture
  Equal $p.Count 0
}
Case 'unknown child creation time excluded' {
  $child=ProcessRecord 201 100 'helper.exe' 'C:\Runtime\helper.exe' ''; $child.CreationDate=$null
  $p=Get-RecoveryOwnedProcesses @($hostRecord,$child) $fixture
  Equal $p.Count 1
}
function ResultState($Mode='normal', $Actions=@('launch','close')) {
  $s=@{mode=$Mode;launches=@($Actions | Where-Object { $_ -eq 'launch' }).Count;events=@();ui=@{}}
  foreach ($a in $Actions) { $e=@{action=$a}; if ($a -ne 'launch') { $e.outcome='passed' }; $s.events+=$e }
  foreach ($name in @('SystemHUD','Party','Combat')) { $s.ui[$name]=@{outcome='passed';launch=$s.launches;evidence='Synthetic observed content'} }
  return $s
}
Case 'normal complete run passes' { Equal (Get-RecoveryResult (ResultState) @()) 'passed' }
Case 'pending UI remains incomplete' { $s=ResultState; $s.ui.Combat.outcome='pending'; Equal (Get-RecoveryResult $s @()) 'incomplete' }
Case 'interrupted UI remains incomplete' { $s=ResultState; $s.ui.Combat.outcome='interrupted'; Equal (Get-RecoveryResult $s @()) 'incomplete' }
Case 'failed UI fails' { $s=ResultState; $s.ui.Party.outcome='failed'; Equal (Get-RecoveryResult $s @()) 'failed' }
Case 'failed UI is not hidden by another pending check' { $s=ResultState; $s.ui.SystemHUD.outcome='pending'; $s.ui.Combat.outcome='failed'; Equal (Get-RecoveryResult $s @()) 'failed' }
Case 'missing UI check cannot pass' { $s=ResultState; $s.ui.Remove('Combat'); Equal (Get-RecoveryResult $s @()) 'incomplete' }
Case 'old-launch UI cannot pass' { $s=ResultState 'normal' @('launch','close','launch','close'); $s.ui.Combat.launch=1; Equal (Get-RecoveryResult $s @()) 'incomplete' }
Case 'remaining processes prevent completion' { Equal (Get-RecoveryResult (ResultState) @($hostRecord)) 'incomplete' }
Case 'timed-out shutdown fails' { $s=ResultState; $s.events[-1].outcome='timed-out'; Equal (Get-RecoveryResult $s @()) 'failed' }
Case 'timeout with residual processes remains failed' { $s=ResultState; $s.events[-1].outcome='timed-out'; Equal (Get-RecoveryResult $s @($hostRecord)) 'failed' }
Case 'latest launch must be closed' { Equal (Get-RecoveryResult (ResultState 'normal' @('launch','close','launch')) @()) 'incomplete' }
Case 'ordered forced recovery passes' { Equal (Get-RecoveryResult (ResultState 'forced' @('launch','terminate','launch','close')) @()) 'passed' }
Case 'two launches before termination are not recovery' { Equal (Get-RecoveryResult (ResultState 'forced' @('launch','launch','terminate','close')) @()) 'incomplete' }
Case 'termination after close is not recovery' { Equal (Get-RecoveryResult (ResultState 'forced' @('launch','close','terminate','launch','close')) @()) 'incomplete' }
Case 'forced run without relaunch is incomplete' { Equal (Get-RecoveryResult (ResultState 'forced' @('launch','terminate','close')) @()) 'incomplete' }
Case 'normal run cannot use termination' { Equal (Get-RecoveryResult (ResultState 'normal' @('launch','terminate','launch','close')) @()) 'incomplete' }
Case 'unobserved evidence cannot pass' { $s=ResultState; $s.ui.SystemHUD.evidence=''; Equal (Get-RecoveryResult $s @()) 'incomplete' }
Case 'launch count mismatch cannot pass' { $s=ResultState; $s.launches=2; Equal (Get-RecoveryResult $s @()) 'incomplete' }
Case 'empty event history cannot pass' { Equal (Get-RecoveryResult (ResultState 'normal' @()) @()) 'incomplete' }
Case 'unrecognized events cannot pass' { Equal (Get-RecoveryResult (ResultState 'normal' @('launch','unknown','close')) @()) 'incomplete' }

# Exercise the real entry point with mocked CIM records, not source-text assertions.
# Only a new temporary directory containing synthetic JSON is written.
$testRoot=Join-Path ([IO.Path]::GetTempPath()) ('navis-recovery-policy-'+[guid]::NewGuid())
New-Item -ItemType Directory -Path (Join-Path $testRoot 'vault') -Force | Out-Null
$entry=Join-Path $PSScriptRoot 'test-packaged-recovery.ps1'
function Write-State($Value) { $Value | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $testRoot 'recovery.json') }
function IntegrationState {
  $s=ResultState 'forced' @('launch','terminate','launch','close')
  $s.run=$testRoot; $s.vault=Join-Path $testRoot 'vault'; $s.exe=Join-Path $testRoot 'release/navis-protocol.exe'
  $s.profile=Join-Path $testRoot 'profile'; $s.python='C:\Runtime\python.exe'; $s.before=@{}
  $s.host=@{pid=100;ticks=$epoch.ToUniversalTime().Ticks}
  return $s
}
try {
  Case 'entry point rejects reused PID before accessing process handle' {
    $s=IntegrationState; Write-State $s
    $global:OfflineRecoveryIdentity=ProcessRecord 100 1 'navis-protocol.exe' $s.exe '' 5
    function Get-CimInstance { return $global:OfflineRecoveryIdentity }
    $message=''
    try { & $entry -Action terminate -RunDirectory $testRoot | Out-Null } catch { $message=$_.Exception.Message }
    Equal $message 'Host PID/path/creation-time ownership mismatch.'
  }
  Case 'entry point rejects stale PID before accessing process handle' {
    $s=IntegrationState; Write-State $s
    function Get-CimInstance { return @() }
    $message=''
    try { & $entry -Action close -RunDirectory $testRoot | Out-Null } catch { $message=$_.Exception.Message }
    Equal $message 'Host PID/path/creation-time ownership mismatch.'
  }
  Case 'entry point report preserves interrupted outcome' {
    $s=IntegrationState; $s.ui.Combat.outcome='interrupted'; Write-State $s
    function Get-CimInstance { return @() }
    & $entry -Action report -RunDirectory $testRoot | Out-Null
    $observed=Get-Content (Join-Path $testRoot 'recovery.json') -Raw | ConvertFrom-Json
    Equal $observed.result 'incomplete'; Equal $observed.ui.Combat.outcome 'interrupted'
  }
  Case 'entry point report rejects invalid forced order' {
    $s=IntegrationState; $s.events=@(@{action='launch'},@{action='launch'},@{action='terminate';outcome='passed'},@{action='close';outcome='passed'}); Write-State $s
    function Get-CimInstance { return @() }
    & $entry -Action report -RunDirectory $testRoot | Out-Null
    Equal ((Get-Content (Join-Path $testRoot 'recovery.json') -Raw | ConvertFrom-Json).result) 'incomplete'
  }
  Case 'entry point report accepts complete synthetic recovery' {
    Write-State (IntegrationState)
    function Get-CimInstance { return @() }
    & $entry -Action report -RunDirectory $testRoot | Out-Null
    $observed=Get-Content (Join-Path $testRoot 'recovery.json') -Raw | ConvertFrom-Json
    Equal $observed.result 'passed'; Equal @($observed.finalProcesses).Count 0
  }
} finally {
  # Exact test-created paths only; no recursive deletion or process cleanup.
  Remove-Item -LiteralPath (Join-Path $testRoot 'recovery.json') -ErrorAction SilentlyContinue
  Remove-Item -LiteralPath (Join-Path $testRoot 'vault')
  Remove-Item -LiteralPath $testRoot
  Remove-Variable OfflineRecoveryIdentity -Scope Global -ErrorAction SilentlyContinue
}
if ($failures.Count) { $failures | ForEach-Object { Write-Output $_ }; throw "$($failures.Count) of $total offline cases failed" }
Write-Output "$total offline recovery policy cases passed. No live processes, UI or network used."
