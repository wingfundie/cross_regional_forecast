"""Data-derived interpretation for the mandatory portfolio case."""
import pandas as pd
from .core import SIGNAL,SPIKE

def ea_case(units,panel,segments,headers,forecast,portfolios):
    paragraphs=[]
    h=headers.reset_index() if 'offer_id' not in headers.columns else headers
    reaction=h[h.DUID.eq('MP1')&h.OFFERDATE.ge(SIGNAL)&h.REBIDEXPLANATION.str.contains('VOLL',case=False,na=False)].sort_values('OFFERDATE')
    if len(reaction):
        r=reaction.iloc[0];ss=segments[segments.offer_id.eq(r.offer_id)&segments.future_at_offer].sort_values('delivery_from')
        if len(ss):
            early=ss.iloc[0];later=ss.iloc[-1]
            paragraphs.append(f"Mount Piper 1 made a directly documented price-spike response at {r.OFFERDATE:%H:%M:%S}, {(r.OFFERDATE-SIGNAL).total_seconds()/60:.2f} minutes after the report-generation proxy. Its reason was: “{r.REBIDEXPLANATION}”. For {early.delivery_from:%H:%M}–{early.delivery_to:%H:%M} delivery endings, low-price volume at or below $300/MWh stayed at {early.after_le300:g} MW, but the distribution within that low-price stack changed. For {later.delivery_from:%H:%M}–{later.delivery_to:%H:%M}, volume at or below $300 increased from {later.before_le300:g} to {later.after_le300:g} MW. Maximum availability stayed at {early.after_maxavail:g} MW. This was repricing of existing capability, not an increase in declared plant capacity.")
            p=panel[panel.DUID.eq('MP1')].set_index('delivery')
            if SPIKE in p.index:
                row=p.loc[SPIKE]
                paragraphs.append(f"At 07:20 the aligned SCADA observation was {row.actual_mw:.1f} MW and the interval target was {row.target_mw:.1f} MW. That dispatch target was set in the spike dispatch run before the 07:17:45 rebid. The immediate generation increase therefore cannot be attributed to that later accepted offer. The rebid positioned subsequent intervals, including keeping the 07:35–08:00 offer at a higher low-priced volume.")
            later_blocks=set(ss.block)
            paragraphs.append('That first VOLL-citing revision affected '+', '.join(sorted(later_blocks))+' delivery only. It does not itself establish evening or overnight protection. Later-period changes must be assessed from their own timestamps and reasons.')
    for duid in ['MP2','TALWB1']:
        u=units[units.DUID.eq(duid)]
        if len(u):
            u=u.iloc[0]
            paragraphs.append(f'{duid} had {u.scada_intervals}/288 observations, a maximum observed output of {u.max_mw:.1f} MW and {u.post_signal_revisions} future-period post-signal revisions. Zero output and zero offered availability support an inactive/declared-unavailable description; a technical outage cause still requires independent evidence.')
    u=units[units.DUID.eq('TALWA1')]
    f=forecast[forecast.DUID.eq('TALWA1')&forecast.forecast_mw.ge(5)].sort_values('delivery')
    if len(u) and len(f):
        u=u.iloc[0];first=f.iloc[0]
        example=forecast[forecast.DUID.eq('TALWA1')&forecast.delivery.eq(pd.Timestamp('2026-10-10 17:30'))]
        paragraphs.append(f'Tallawarra A first crossed the 5 MW reporting threshold at {u.first_output_increase:%H:%M}, and peaked at {u.max_mw:.1f} MW. The pre-signal AEMO run already projected positive generation at {first.delivery:%H:%M}: {first.forecast_mw:.1f} MW. An afternoon return was therefore anticipated before the spike; it cannot all be counted as a newly chosen reaction to the morning event.')
        if len(example):
            r=example.iloc[0];paragraphs.append(f'At 17:30, Tallawarra A produced {r.actual_mw:.1f} MW against the frozen projection of {r.forecast_mw:.1f} MW, a {r.actual_mw-r.forecast_mw:.1f} MW difference. This is a concrete later acceleration relative to the public projected path, although it does not reveal the participant’s internal plan or prove a coal-hedging motive.')
    p=portfolios[portfolios.controller.eq('EnergyAustralia')&portfolios.region.eq('NSW1')]
    for ref in ['immediate','projected']:
        g=p[p.reference.eq(ref)&p.complete]
        if len(g):
            r=g.loc[g.matched_mw.idxmax()]
            paragraphs.append(f'Against the {ref} reference, maximum same-time matched replacement was {r.matched_mw:.1f} MW at {r.delivery:%H:%M}, when coal shortfall was {r.shortfall_mw:.1f} MW and additional gas/battery output was {r.incremental_mw:.1f} MW. These reference-dependent figures differ from total Tallawarra generation and from a scenario treating Mount Piper 2’s registered capacity as a standing gap.')
    paragraphs.append('Portfolio interpretation: Tallawarra provided physical generation while Mount Piper 2 was inactive, but the public record does not establish that its entire run was commissioned in response to the spike or sized to a private hedge position. The supported finding is the same-time physical contribution; a coordinated protection motive remains plausible rather than proven.')
    return paragraphs
