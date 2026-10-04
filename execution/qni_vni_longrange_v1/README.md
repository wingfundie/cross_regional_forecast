# QNI/VNI long-range improvement campaign

Run from the repository root:

```text
python -m nemic.longrange extract-mtpasa --horizon-days 90 --latest-generation 2026-06-03T00:00:00+10:00
python -m nemic.longrange_campaign prepare
python -m nemic.longrange_campaign run --connector VNI
python -m nemic.longrange_campaign run --connector QNI
python -m nemic.longrange_campaign report
python -m nemic.longrange_campaign status
python -m nemic.longrange_campaign shadow --connector VNI --origin 2026-10-04T08:00:00+10:00 --output local_exports/vni_shadow_20261004
```

The state file and content hashes under `data/forecast_experiments/qni_vni_longrange_v1/` are authoritative. A completed historical run remains research-only and does not activate production routes.

After both connector policies exist, `scripts/collect_longrange_inputs.ps1` acquires the latest public MT PASA file for the next 08:00 NEM issue and records completed receipt time. Run it before the issue cutoff (for example 05:45 Singapore); a later receipt is correctly ineligible for that issue. `scripts/run_daily_longrange_shadow.ps1` then performs one single-worker daily cycle and writes VNI and QNI curves. With no explicit origin it uses 08:00 fixed NEM time (06:00 Singapore). Locks prevent overlapping collection and forecast cycles. Run both successfully before attaching them to any external scheduler; all outputs remain research-only under `local_exports/daily_shadow/`.
