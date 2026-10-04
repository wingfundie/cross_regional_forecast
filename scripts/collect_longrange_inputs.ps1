$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $projectRoot
$lockPath = Join-Path $projectRoot "data/forecast_inputs/qni_vni_longrange/collector.lock"
[IO.Directory]::CreateDirectory((Split-Path -Parent $lockPath)) | Out-Null
$lock = $null; $ownsLock = $false
try {
    $lock = [IO.File]::Open($lockPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    $ownsLock = $true
    $nemNow = [DateTimeOffset]::UtcNow.ToOffset([TimeSpan]::FromHours(10))
    $issueDay = if ($nemNow.Hour -lt 8) { $nemNow.Date } else { $nemNow.Date.AddDays(1) }
    $nextIssue = [DateTimeOffset]::new($issueDay.Year, $issueDay.Month, $issueDay.Day, 8, 0, 0, [TimeSpan]::FromHours(10))
    python -m nemic.longrange collect-current --origin $nextIssue.ToString("yyyy-MM-ddTHH:mm:sszzz") --horizon-days 90
    if ($LASTEXITCODE -ne 0) { throw "Current public MT PASA acquisition failed" }
}
finally {
    if ($lock) { $lock.Dispose() }
    if ($ownsLock -and (Test-Path -LiteralPath $lockPath)) { Remove-Item -LiteralPath $lockPath -Force }
}
