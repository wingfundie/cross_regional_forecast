param(
    [Parameter(Mandatory = $true)]
    [int]$VniProcessId
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $repoRoot

$env:LOKY_MAX_CPU_COUNT = '2'
$env:OMP_NUM_THREADS = '2'
$env:MKL_NUM_THREADS = '2'
$env:OPENBLAS_NUM_THREADS = '2'
$env:NUMEXPR_NUM_THREADS = '2'

$runRoot = Join-Path $repoRoot 'data/forecast_experiments/qni_vni_clustering_v1'
$statePath = Join-Path $runRoot 'continuation_status.json'
$logPath = Join-Path $runRoot 'continuation.log'

function Write-ContinuationState {
    param(
        [string]$Stage,
        [string]$Status,
        [string]$Detail
    )
    $payload = [ordered]@{
        campaign = 'qni_vni_clustering_v1'
        stage = $Stage
        status = $Status
        detail = $Detail
        updated_at = [DateTimeOffset]::Now.ToString('o')
        vni_process_id = $VniProcessId
        process_id = $PID
    }
    $json = $payload | ConvertTo-Json -Depth 5
    [IO.File]::WriteAllText($statePath, $json, [Text.UTF8Encoding]::new($false))
}

function Read-RequiredSummary {
    param(
        [string]$Path,
        [string]$Connector
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Connector summary is missing: $Path"
    }
    $summary = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    if ($summary.status -ne 'complete' -or $summary.stage -ne 'all') {
        throw "$Connector all-stage run is not complete (status=$($summary.status), stage=$($summary.stage))"
    }
    if (@($summary.failures).Count -ne 0) {
        throw "$Connector summary contains failed jobs"
    }
    return $summary
}

try {
    $owner = Get-Process -Id $VniProcessId -ErrorAction SilentlyContinue
    if ($null -ne $owner) {
        Write-ContinuationState 'VNI' 'waiting' "Waiting for healthy VNI owner PID $VniProcessId"
        Wait-Process -Id $VniProcessId
    }

    $vniSummaryPath = Join-Path $runRoot 'run/VNI/summary.json'
    $null = Read-RequiredSummary $vniSummaryPath 'VNI'
    Write-ContinuationState 'VNI' 'complete' 'Verified VNI all-stage summary with no failed jobs'

    $qniSummaryPath = Join-Path $runRoot 'run/QNI/summary.json'
    $qniComplete = $false
    if (Test-Path -LiteralPath $qniSummaryPath) {
        try {
            $null = Read-RequiredSummary $qniSummaryPath 'QNI'
            $qniComplete = $true
        }
        catch {
            $qniComplete = $false
        }
    }

    if (-not $qniComplete) {
        $activeQni = @(
            Get-CimInstance Win32_Process |
                Where-Object {
                    $_.Name -match '^python' -and
                    $_.CommandLine -match 'nemic\.experiments\.clustering run --connector QNI'
                }
        )
        if ($activeQni.Count -gt 1) {
            throw 'Multiple QNI campaign owners detected'
        }
        if ($activeQni.Count -eq 1) {
            Write-ContinuationState 'QNI' 'waiting' "Waiting for existing QNI owner PID $($activeQni[0].ProcessId)"
            Wait-Process -Id $activeQni[0].ProcessId
        }
        else {
            Write-ContinuationState 'QNI' 'running' 'Starting gated QNI all-stage replication'
            & python -m nemic.experiments.clustering run --connector QNI --stage all 2>&1 |
                Tee-Object -FilePath $logPath -Append |
                Out-Null
            if ($LASTEXITCODE -ne 0) {
                throw "QNI campaign exited with code $LASTEXITCODE"
            }
        }
    }

    $null = Read-RequiredSummary $qniSummaryPath 'QNI'
    Write-ContinuationState 'QNI' 'complete' 'Verified QNI all-stage summary with no failed jobs'

    Write-ContinuationState 'report' 'running' 'Rebuilding cached report from VNI and QNI evidence'
    & python -m nemic.experiments.clustering report 2>&1 |
        Tee-Object -FilePath $logPath -Append |
        Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Report build exited with code $LASTEXITCODE"
    }

    $validationText = (& python -m nemic.experiments.clustering validate 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) {
        throw "Report validation exited with code $LASTEXITCODE"
    }
    $validation = $validationText | ConvertFrom-Json
    if (-not $validation.valid) {
        throw "Report validation failed: $($validation.errors -join '; ')"
    }
    $validationText | Add-Content -LiteralPath $logPath -Encoding utf8
    Write-ContinuationState 'complete' 'complete' 'VNI, QNI and cached report validation completed'
}
catch {
    Write-ContinuationState 'continuation' 'failed' $_.Exception.Message
    $_ | Out-String | Add-Content -LiteralPath $logPath -Encoding utf8
    exit 1
}
