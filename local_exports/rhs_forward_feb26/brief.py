"""Build and validate the compact offline brief from cached pilot rows."""
from pathlib import Path
import json, hashlib
import pandas as pd
import markdown
from bs4 import BeautifulSoup
from urllib.parse import urlsplit
P=Path(__file__).resolve().parent
d=pd.read_csv(P/'predictions.csv',parse_dates=['slot','issue'])
m=pd.read_csv(P/'metrics.csv')
o=pd.read_csv(P/'observations.csv',parse_dates=['end','created','modified'])
f=pd.read_csv(P/'issued_forecasts.csv',parse_dates=['end','created','modified'])
a=pd.read_csv(P/'origins.csv',parse_dates=['created','modified'])
assert f.run.nunique()==15 and len(a)==15 and not f.duplicated(['product','end']).any()
assert (f[['created','modified']].max(axis=1)<f.end-pd.Timedelta(minutes=5)).all()
asof=f.merge(a,on='run',suffixes=('_forecast','_prior'))
assert (asof[['created_prior','modified_prior']].max(axis=1)<=asof.created_forecast).all()
c=pd.read_csv(P.parents[1]/'reports/rhs_replay/cases/replay.csv')
c['end']=pd.to_datetime(c.interval_end).dt.tz_localize(None)
check=c[c.end.dt.day.eq(19)].merge(o,on='end')
for eq,col in [('DATASNAP_DFS_NSYD','sydney'),('N::Q_NIL_KC','terr')]:
    g=check[check.equation.eq(eq)]
    assert len(g)==24 and (g[col]-g.demand_mw).abs().max()<1e-5
    if col=='terr':assert (g.rhs-g.rhs_reference).abs().max()<1e-5
scores=d.groupby(['target','product','method']).error.apply(lambda x:x.abs().mean())
assert (scores-m.set_index(['target','product','method']).mae).abs().max()<1e-7
def table(product):
    z=m[m['product'].eq(product)].pivot(index='method',columns='target',values='mae').reindex(
       ['Population share','Fixed historical share','Clock and day-type share','Clock and day-type level','Latest public reading','Latest reading plus regional change','Issued AEMO'])
    z.columns=['Network RHS','Sydney-area load','Terranora load']
    return z[['Sydney-area load','Terranora load','Network RHS']].to_markdown(floatfmt='.1f',missingval='—').replace('nan','—')
txt=f"""# Forward constraint RHS from regional demand forecasts

## Finding

Regional demand can drive a local-load estimate and a conditional network RHS. Current public predispatch files also contain local demand forecasts for two named inputs. For a custom regional forecast, these offer an electrical starting point. Population is a fallback where a matching load history or issued local forecast is missing.

## Day-ahead results

Mean absolute error in MW across 12 half-hours. The three previous-afternoon forecasts were generated about 16:02 NEM time and the delivery half-hours ended between 10:30 and 12:00 the next day. Leads were 18.5–20 hours to interval end.

{table('PREDISPATCHIS')}

## Short-horizon results

Mean absolute error in MW on the same deliveries. The 12 P5MIN runs were generated 34–60 minutes before the native five-minute delivery endpoints (rounded). Each group of six predictions came from one coherent run. Scores below use half-hour averages.

{table('P5MIN')}

## How the comparisons were made

- Training used the seven prior mornings of 9–15 February 2026. Evaluation used 19, 20 and 22 February. Four complete six-interval blocks were scored on each morning, in fixed NEM time. The 19th revisits a previously identified congestion day. This is an exploratory targeted sample.
- NSW and Queensland forecast inputs are the contemporary AEMO run's TOTALDEMAND. The fixed share is the ratio of total historical local MW to historical NSW MW over the calibration mornings. The matched share and matched level use the same delivery half-hour and weekday/weekend class, with five weekday or two weekend training dates. The fixed share is morning-specific. Additional calibration seasons and hours would be needed for whole-day use.
- The population benchmark uses June 2024 ABS Significant Urban Areas: Sydney 5,143,256, Newcastle–Maitland 534,033, and Wollongong 318,258. The denominator is the NSW and ACT resident population (8,953,169), an approximate geography for NSW1. The fraction is 66.97%. This proxy deliberately tests a geographic approximation to the AEMO three-city signal. No Western Sydney-only electrical boundary was assumed. [ABS source released March 2025](https://www.abs.gov.au/statistics/people/population/regional-population/2023-24)
- Actuals are averages of the six five-minute dispatch RHS values or decoded monitor observations. For the 19th, both load readings and the network RHS were independently cross-checked against the earlier NEMDE replay. The 20th and 22nd use the published monitor signal as reference. These are effective quantities in the market solution.
- The previous-reading alternatives use an original public file created before the forecast was issued. The change method adds the training share times the forecast change in NSW demand to the earlier measured local load. Its network variant anchors to the previously observed RHS, applies the nonlinear formula change, holds interconnector flow at its observed value and treats forecast regional MW changes as approximate R-term changes. It uses no future local reading, flow or LHS.
- For the full N::Q_NIL_KC RHS under regional-only inputs, the fixed-share and matched-share methods use the estimated Terranora load, the average signed initial flow from corresponding training intervals, and forecast NSW and Queensland TOTALDEMAND as approximations for their constraint R terms. Forecasts of scheduled load and network topology were not supplied. Expected flow, the definition of regional demand and local-load error all contribute to full RHS error. The matched-level and previous-reading benchmarks use earlier observed RHS values directly. The issued AEMO comparator uses the same original run as the regional inputs.
- Each source file has a creation stamp and archived file time. Both precede the delivery interval. The original recipient's download time is unknown. Three February mornings cannot establish year-round accuracy, binding precision or a prediction interval. Half-hour average error can hide a five-minute binding event.

## How to drive a calculator

1. Match the dispatch or predispatch version, scope and typed input. In the verified predispatch monitors, `DATASNAP_DFS_NSYD.RHS − 10000` gives the effective entered `N_SYDNEY` value and `DATASNAP_TE_967_1.RHS − 10000` gives `N_TERRANORA`. Preserve the run, delivery interval and version. Each formula has a fallback default. Use the published constraint RHS itself as the benchmark for the unmodified equation. [AEMO predispatch files](https://www.aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem/market-management-system-mms-data/pre-dispatch) · [Verified program terms](monitor_definitions.csv)
2. Where there is no issued local series, estimate a historical electrical load share by delivery period, weekday/weekend and season. Keep a simpler fixed share as the benchmark. Near dispatch, test the last local reading plus a forecast regional change against persistence. Negative local net flow is possible: Terranora averaged below zero in seven of the twelve evaluated half-hours.
3. When using your own regional forecast with an AEMO base case, try local scenario = AEMO local forecast + historical local response × (your regional forecast − AEMO regional forecast). Fit the response to historical *changes* at matched hours and backtest it. This proposed scenario adjustment was not scored with a private forecast. Use a common regional demand definition and forecast vintage.
4. For a new Western Sydney footprint, use mapped customer connections or population as starting weights for the residential component. Add commercial profiles, explicit large sites and embedded generation to model net draw. Use mapped feeder/substation load to calibrate. Match electrical boundaries before aggregating and check for overlapping meters. A regional forecast already net of rooftop PV requires care to avoid subtracting the same solar generation twice. [Endeavour planning data](https://dapr.endeavourenergy.com.au/) · [CER postcode solar data](https://cer.gov.au/markets/reports-and-data/small-scale-installation-postcode-data)
5. For a missing switch or outage state, evaluate separate state-specific RHS values. For a missing continuous flow or rating, use a historical range conditional on comparable grid conditions. Evaluate the complete equation for each coherent scenario, including nonlinear terms. At longer horizons use held-out forecast residuals by lead and delivery period for calibrated ranges. A binding assessment also requires an invoked equation and a forecast of signed LHS headroom. The results above score RHS and local load only.

[Issued forecast rows](issued_forecasts.csv) · [Dispatch observations](observations.csv) · [Forecast-by-forecast comparisons](predictions.csv) · [Bias, MAE and maximum errors](metrics.csv) · [Source hashes](sources.json) · [Prior reading hashes](origin_sources.json) · [Reproduction script](study.py)
"""
(P/'brief.md').write_text(txt,encoding='utf8')
body=markdown.markdown(txt,extensions=['tables']).replace('<table>','<div class="scroll"><table>').replace('</table>','</table></div>')
html='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Forward RHS from regional forecasts</title><style>html{background:#f3f5f6;color:#172e38;font:16px/1.55 system-ui}main{max-width:960px;margin:auto;padding:clamp(16px,4vw,64px);background:white}h1{font-size:clamp(32px,5vw,52px);line-height:1.1}h2{margin-top:1.8em;color:#165866}li{margin:.7em 0}a{color:#08688a}code{overflow-wrap:anywhere}.scroll{overflow:auto}table{min-width:600px;border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}td,th{padding:.5em;border-bottom:1px solid #d9e3e6}th{background:#eaf1f2}td:first-child,th:first-child{text-align:left}</style><main>'+body+'</main></html>'
(P/'index.html').write_text(html,encoding='utf8')
for a in BeautifulSoup(html,'html.parser').select('a[href]'):
    u=urlsplit(a['href'])
    if not u.scheme:assert (P/u.path).is_file(),u.path
print('Verified 15 issued runs, 12 half-hours per horizon, measured baselines, archive-only timing, 19 February reference evidence and local links.')
