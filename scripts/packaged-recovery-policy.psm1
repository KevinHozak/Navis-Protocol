# Pure policy functions: no process, filesystem, UI or network operations.
function Test-RecoveryHostIdentity($Identity, $Saved, [string]$Executable) {
  return [bool]($Identity -and $Saved -and $Identity.ProcessId -eq $Saved.pid -and
    $Identity.ExecutablePath -eq $Executable -and $Identity.CreationDate -and
    $Identity.CreationDate.ToUniversalTime().Ticks -eq $Saved.ticks)
}

function Get-RecoveryOwnedProcesses([object[]]$Processes, $State) {
  $owned=@($Processes | Where-Object {
    if (!$_.CreationDate) { return $false }
    if ($_.ExecutablePath -eq $State.exe) { return $true }
    # Parse whole command tokens; a sibling path or diagnostic mention is not ownership.
    $arguments=@([regex]::Matches([string]$_.CommandLine, '(?:"[^"]*"|[^\s"]+)+') | ForEach-Object { $_.Value.Trim('"') })
    if ($_.Name -eq 'msedgewebview2.exe') {
      foreach ($argument in $arguments) {
        if ($argument.StartsWith('--user-data-dir=',[StringComparison]::OrdinalIgnoreCase)) {
          $path=$argument.Substring('--user-data-dir='.Length).Trim('"')
          if (Test-RecoveryChildPath $path $State.profile) { return $true }
        }
      }
    }
    if ($_.Name -eq 'python.exe' -and $_.ExecutablePath -eq $State.python) {
      foreach ($argument in $arguments) {
        if ($argument.EndsWith('.py',[StringComparison]::OrdinalIgnoreCase) -and (Test-RecoveryChildPath $argument (Join-Path $State.run 'release/backend'))) { return $true }
      }
    }
    return $false
  })
  do {
    $count=$owned.Count
    $children=@($Processes | Where-Object { $child=$_; $child.CreationDate -and @($owned | Where-Object { $child.ParentProcessId -eq $_.ProcessId -and $child.CreationDate -ge $_.CreationDate }).Count -gt 0 })
    $owned=@($owned+$children | Sort-Object ProcessId -Unique)
  } while ($owned.Count -gt $count)
  return ,$owned
}

function Test-RecoveryChildPath([string]$Path,[string]$Root) {
  if ([string]::IsNullOrWhiteSpace($Path) -or [string]::IsNullOrWhiteSpace($Root) -or ![IO.Path]::IsPathFullyQualified($Path)) { return $false }
  try {
    $pathValue=[IO.Path]::GetFullPath($Path)
    $rootValue=[IO.Path]::GetFullPath($Root).TrimEnd('\','/')
    return $pathValue.Equals($rootValue,[StringComparison]::OrdinalIgnoreCase) -or $pathValue.StartsWith($rootValue+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)
  } catch { return $false }
}

function Get-RecoveryResult($State, [object[]]$Processes) {
  if (@($State.events | Where-Object { $_.outcome -eq 'timed-out' }).Count) { return 'failed' }
  if ($Processes.Count) { return 'incomplete' }
  if ($State.mode -notin @('normal','forced')) { return 'incomplete' }
  $running=$false; $armed=$false; $recovered=$false; $launches=0
  foreach ($event in $State.events) {
    switch ($event.action) {
      'launch' {
        if ($running) { return 'incomplete' }
        $running=$true; $launches++; $recovered=$armed; $armed=$false
      }
      'terminate' {
        if (!$running -or $State.mode -ne 'forced' -or $event.outcome -ne 'passed') { return 'incomplete' }
        $running=$false; $armed=$true
      }
      'close' {
        if (!$running -or $event.outcome -ne 'passed') { return 'incomplete' }
        $running=$false
      }
      default { return 'incomplete' }
    }
  }
  if (!$State.events.Count -or $State.events[-1].action -ne 'close' -or $launches -ne $State.launches -or ($State.mode -eq 'forced' -and !$recovered)) { return 'incomplete' }
  foreach ($name in @('SystemHUD','Party','Combat')) {
    $check=$State.ui[$name]
    if ($check -and $check.launch -eq $launches -and $check.outcome -eq 'failed') { return 'failed' }
  }
  foreach ($name in @('SystemHUD','Party','Combat')) {
    $check=$State.ui[$name]
    if (!$check -or $check.launch -ne $launches -or [string]::IsNullOrWhiteSpace($check.evidence)) { return 'incomplete' }
    if ($check.outcome -ne 'passed') { return 'incomplete' }
  }
  return 'passed'
}

Export-ModuleMember -Function Test-RecoveryHostIdentity,Get-RecoveryOwnedProcesses,Get-RecoveryResult
