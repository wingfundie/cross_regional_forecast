param(
    [Parameter(Mandatory = $true)]
    [int]$DiscoveryProcessId
)

$ErrorActionPreference = 'Stop'
$workspace = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$discoveryManifest = Join-Path $workspace 'data\forecast_experiments\qni_vni_fundamentals_v3\balanced\VNI\balanced-v1\discovery_manifest.json'

Wait-Process -Id $DiscoveryProcessId -ErrorAction SilentlyContinue
if (-not (Test-Path -LiteralPath $discoveryManifest)) {
    throw 'Balanced VNI discovery did not produce its verified manifest; downstream stages were not started.'
}

$env:OMP_NUM_THREADS = '2'
$env:MKL_NUM_THREADS = '2'
$env:OPENBLAS_NUM_THREADS = '2'
$env:NUMEXPR_NUM_THREADS = '2'

Push-Location $workspace
try {
    foreach ($stage in @('confirmation', 'sensitivity', 'score')) {
        & python -m nemic.fundamentals balanced --connector VNI --stage $stage --workers 1 --resume
        if ($LASTEXITCODE -ne 0) {
            throw "Balanced VNI stage failed: $stage"
        }
    }
}
finally {
    Pop-Location
}
