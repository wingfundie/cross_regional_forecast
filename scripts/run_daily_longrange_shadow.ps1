param(
    [string]$Origin,
    [string]$OutputRoot = "local_exports/daily_shadow"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $projectRoot
$lockPath = Join-Path $projectRoot "data/forecast_experiments/qni_vni_longrange_v1/daily_shadow.lock"
$lockDirectory = Split-Path -Parent $lockPath
[IO.Directory]::CreateDirectory($lockDirectory) | Out-Null
$lock = $null
$ownsLock = $false

try {
    $lock = [IO.File]::Open($lockPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    $ownsLock = $true
    $owner = [Text.Encoding]::UTF8.GetBytes("pid=$PID started=$([DateTimeOffset]::UtcNow.ToString('o'))")
    $lock.Write($owner, 0, $owner.Length)
    $lock.Flush()

    $env:OMP_NUM_THREADS = "2"
    $env:MKL_NUM_THREADS = "2"
    $env:OPENBLAS_NUM_THREADS = "2"
    if (-not $Origin) {
        $nemNow = [DateTimeOffset]::UtcNow.ToOffset([TimeSpan]::FromHours(10))
        $originValue = [DateTimeOffset]::new($nemNow.Year, $nemNow.Month, $nemNow.Day, 8, 0, 0, [TimeSpan]::FromHours(10))
        $Origin = $originValue.ToString("yyyy-MM-ddTHH:mm:sszzz")
    }
    $originDate = [DateTimeOffset]::Parse($Origin).ToOffset([TimeSpan]::FromHours(10)).ToString("yyyyMMdd")
    $runRoot = Join-Path $OutputRoot $originDate
    if (Test-Path -LiteralPath $runRoot) {
        throw "Shadow output already exists: $runRoot"
    }

    python -m nemic.longrange collect-current --origin $Origin --horizon-days 90
    if ($LASTEXITCODE -ne 0) { throw "Current public MT PASA acquisition failed" }
    python -m nemic.longrange_campaign shadow --connector VNI --origin $Origin --output (Join-Path $runRoot "VNI")
    if ($LASTEXITCODE -ne 0) { throw "VNI shadow forecast failed" }
    python -m nemic.longrange_campaign shadow --connector QNI --origin $Origin --output (Join-Path $runRoot "QNI")
    if ($LASTEXITCODE -ne 0) { throw "QNI shadow forecast failed" }
}
finally {
    if ($lock) { $lock.Dispose() }
    if ($ownsLock -and (Test-Path -LiteralPath $lockPath)) { Remove-Item -LiteralPath $lockPath -Force }
}
