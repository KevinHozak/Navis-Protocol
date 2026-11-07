#requires -Version 7.0
[CmdletBinding()]
param(
  [Parameter(Mandatory)][ValidateSet('prepare','launch','terminate','close','ui','report')][string]$Action,
  [Parameter(Mandatory)][string]$RunDirectory,
  [ValidateSet('normal','forced')][string]$Mode='normal',
  [string]$ReleaseDirectory,
  [string]$Python,
  [ValidateSet('SystemHUD','Party','Combat')][string]$Check,
  [ValidateSet('passed','failed','interrupted')][string]$Outcome,
  [string]$Evidence,
  [ValidateRange(5,120)][int]$ShutdownTimeoutSeconds=45
)
$ErrorActionPreference='Stop'
Import-Module (Join-Path $PSScriptRoot 'packaged-recovery-policy.psm1') -Force
$repo=Split-Path $PSScriptRoot -Parent
$run=[IO.Path]::GetFullPath($RunDirectory)
$statePath=Join-Path $run 'recovery.json'
function Save { $script:state | ConvertTo-Json -Depth 15 | Set-Content -LiteralPath $statePath -Encoding utf8 }
function Hashes($directory) {
  $result=@{}
  Get-ChildItem -LiteralPath $directory -File -Recurse | ForEach-Object {
    $result[[IO.Path]::GetRelativePath($directory,$_.FullName)]=(Get-FileHash -LiteralPath $_.FullName).Hash
  }
  return $result
}
if ($Action -eq 'prepare') {
  if (Test-Path -LiteralPath $run) { throw 'Use a new run directory; existing evidence is never overwritten.' }
  if (!$ReleaseDirectory) { $ReleaseDirectory=Join-Path $repo 'frontend/src-tauri/target/release' }
  if (!$Python) { $Python=Join-Path $repo 'backend/.venv/Scripts/python.exe' }
  $Python=(Resolve-Path -LiteralPath $Python).Path
  $source=(Resolve-Path -LiteralPath $ReleaseDirectory).Path
  $exeSource=Join-Path $source 'navis-protocol.exe'
  if (!(Test-Path -LiteralPath $exeSource)) { throw 'Packaged EXE missing; build it first.' }
  $config=Get-Content (Join-Path $repo 'frontend/src-tauri/tauri.conf.json') -Raw | ConvertFrom-Json -AsHashtable
  foreach ($target in $config.bundle.resources.Values) {
    if (!(Test-Path -LiteralPath (Join-Path $source $target))) { throw "Packaged resource missing: $target" }
  }
  $vault=Join-Path $run 'vault'; $release=Join-Path $run 'release'
  New-Item -ItemType Directory -Path $release -Force | Out-Null
  Copy-Item -LiteralPath $exeSource -Destination $release
  foreach ($target in $config.bundle.resources.Values) {
    $destination=Join-Path $release $target
    New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $source $target) -Destination $destination
  }
  foreach ($folder in @('Bridge','Keeper','Companions','Operations','Battle','Codex/Beasts/Sentinel','Journal/2026/11')) {
    New-Item -ItemType Directory -Path (Join-Path $vault $folder) -Force | Out-Null
  }
  $files=@{
    'Bridge/settings.json'=@{timezone='America/Chicago';lexicon=@{pillars=@{COMMAND='Command';CHRONICLE='Chronicle';CODEX='Codex'}};paths=@{journal_root=(Join-Path $vault 'Journal');operations_dir=(Join-Path $vault 'Operations')}}
    'Bridge/status.json'=@{last_updated='2026-11-07';current_realm='Synthetic Earth';squad=@();tasks=@()}
    'Bridge/CompanionStats.json'=@{companions=@{Keeper=@{xp=0;level=1}}}
    'Bridge/ops_state.json'=@{active_tasks=@();tasks=@()}
    'Battle/battle_state.json'=@{hand=@();discard=@();lost=@();active_links=@{}}
    'Battle/Cards.json'=@{cards=@()}
    'Codex/Beasts/Sentinel/Combat.json'=@{hp=8;attack=1;intent_pattern=@('Strike');affinity='Physical'}
    'Codex/Beasts/Sentinel/beast_data.json'=@{name='Sentinel';tags=@()}
  }
  foreach ($entry in $files.GetEnumerator()) { $entry.Value | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $vault $entry.Key) -Encoding utf8 }
  '# Synthetic Keeper' | Set-Content (Join-Path $vault 'Keeper/Profile.md')
  '# Synthetic Sentinel' | Set-Content (Join-Path $vault 'Codex/Beasts/Sentinel/Profile.md')
  "# Synthetic journal`n## The Sanctum`n- [ ] Synthetic recovery task" | Set-Content (Join-Path $vault 'Journal/2026/11/2026-11-07.md')
  $script:state=@{schema=1;mode=$Mode;run=$run;vault=$vault;exe=(Join-Path $release 'navis-protocol.exe');python=$Python;profile=(Join-Path $run 'profile');sha256=(Get-FileHash $exeSource).Hash;before=(Hashes $vault);events=@();ui=@{};uiHistory=@();launches=0;cloudGeneration='disabled-unconfigured'}
  foreach ($name in @('SystemHUD','Party','Combat')) { $state.ui[$name]=@{outcome='pending';evidence='Not observed'} }
  Save; Write-Output $statePath; exit
}
$script:state=Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json -AsHashtable
if ($Action -ne 'report') { $state.result='incomplete' }
if ($state.run -ne $run -or $state.vault -ne (Join-Path $run 'vault') -or [IO.Path]::GetFullPath($state.exe) -ne [IO.Path]::GetFullPath((Join-Path $run 'release/navis-protocol.exe')) -or $state.profile -ne (Join-Path $run 'profile')) { throw 'Run paths do not match the isolated layout.' }
function Snapshot {
  $all=@(Get-CimInstance Win32_Process)
  $owned=Get-RecoveryOwnedProcesses $all $state
  return ,@($owned | Select-Object ProcessId,ParentProcessId,Name,CreationDate,ExecutablePath,CommandLine)
}
if ($Action -eq 'launch') {
  $existing=Snapshot
  if ($existing.Count) { throw 'Owned processes remain; inspect them before launching again.' }
  $info=[Diagnostics.ProcessStartInfo]::new($state.exe)
  $info.UseShellExecute=$false; $info.WorkingDirectory=Split-Path $state.exe -Parent; $info.WindowStyle='Normal'
  $info.Environment.Clear()
  foreach ($key in @('PATH','SystemRoot','TEMP','TMP','USERPROFILE','APPDATA','LOCALAPPDATA')) { if ([Environment]::GetEnvironmentVariable($key)) { $info.Environment[$key]=[Environment]::GetEnvironmentVariable($key) } }
  $info.Environment['NAVIS_ROOT']=$state.vault; $info.Environment['NAVIS_PYTHON']=$state.python
  $info.Environment['WEBVIEW2_USER_DATA_FOLDER']=$state.profile; $info.Environment['NAVIS_AI_PROVIDER']='openrouter'
  $process=[Diagnostics.Process]::Start($info)
  $identity=Get-CimInstance Win32_Process -Filter "ProcessId=$($process.Id)"
  $state.host=@{pid=$process.Id;ticks=$identity.CreationDate.ToUniversalTime().Ticks}
  $state.launches++; $state.uiHistory+=@{launch=$state.launches-1;checks=$state.ui}
  $state.ui=@{}; foreach ($name in @('SystemHUD','Party','Combat')) { $state.ui[$name]=@{outcome='pending';evidence='Not observed for this launch'} }
  $state.events+=@{action='launch';utc=[datetime]::UtcNow.ToString('o');pid=$process.Id}
  Save; Write-Output "Launched fixture PID $($process.Id). UI checks remain pending."; exit
}
if ($Action -in @('terminate','close')) {
  if ($Action -eq 'terminate' -and $state.mode -ne 'forced') { throw 'Terminate requires a forced-mode run.' }
  $identity=Get-CimInstance Win32_Process -Filter "ProcessId=$($state.host.pid)"
  if (!(Test-RecoveryHostIdentity $identity $state.host $state.exe)) { throw 'Host PID/path/creation-time ownership mismatch.' }
  $process=Get-Process -Id $state.host.pid
  $timer=[Diagnostics.Stopwatch]::StartNew(); $samples=@(); $hostExit=$null
  if ($Action -eq 'terminate') { $process.Kill() } elseif (!$process.CloseMainWindow()) { throw 'No closeable fixture window.' }
  do {
    $process.Refresh(); if ($process.HasExited -and $null -eq $hostExit) { $hostExit=$timer.Elapsed.TotalSeconds }
    $owned=Snapshot
    $samples+=@{elapsedSeconds=$timer.Elapsed.TotalSeconds;utc=[datetime]::UtcNow.ToString('o');processes=$owned}
    if (!$owned.Count) { break }
    Start-Sleep -Milliseconds 500
  } while ($timer.Elapsed.TotalSeconds -lt $ShutdownTimeoutSeconds)
  $state.events+=@{action=$Action;hostExitObservedSeconds=$hostExit;allExitedObservedSeconds=$(if (!$owned.Count) { $timer.Elapsed.TotalSeconds } else { $null });timeoutSeconds=$ShutdownTimeoutSeconds;outcome=$(if (!$owned.Count) {'passed'} else {'timed-out'});samples=$samples}
  Save
  if ($owned.Count) { throw 'Shutdown timed out; evidence and remaining processes retained. No broad kill was attempted.' }
  Write-Output "Host exit observed $([math]::Round($hostExit,3))s; all owned processes exited by $([math]::Round($state.events[-1].allExitedObservedSeconds,3))s."; exit
}
if ($Action -eq 'ui') {
  if (!$Check -or !$Outcome -or [string]::IsNullOrWhiteSpace($Evidence)) { throw 'UI recording requires Check, Outcome and Evidence from an actual observation.' }
  $state.uiHistory+=@{check=$Check;previous=$state.ui[$Check];launch=$state.launches}
  $state.ui[$Check]=@{outcome=$Outcome;evidence=$Evidence;utc=[datetime]::UtcNow.ToString('o');launch=$state.launches}
  Save; exit
}
if ($Action -eq 'report') {
  $after=Hashes $state.vault
  $state.integrity=@{changed=@($state.before.Keys | Where-Object { $after[$_] -ne $state.before[$_] });added=@($after.Keys | Where-Object { !$state.before.ContainsKey($_) })}
  $state.finalProcesses=Snapshot
  $state.result=Get-RecoveryResult $state $state.finalProcesses
  Save; Write-Output "Result: $($state.result). See $statePath"
}
