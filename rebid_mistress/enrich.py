"""Post-reconstruction audits and compact contextual evidence."""
import numpy as np
from .core import *

def prospective_segments(seg):
    """A running dispatch interval is not newly available for normal prospective bidding."""
    rows=[]
    for r in seg.to_dict('records'):
        first_allowed=START+pd.Timedelta(minutes=5*(int(np.ceil((pd.Timestamp(r['offer_time'])-START).total_seconds()/300))+1))
        if r['delivery_from']<first_allowed<=r['delivery_to']:
            left=dict(r);left['delivery_to']=first_allowed-pd.Timedelta(minutes=5);left['period_to']=int((left['delivery_to']-START).total_seconds()/300);left['future_at_offer']=False;left['segment_id']+='-elapsed';rows.append(left)
            r['delivery_from']=first_allowed;r['period_from']=int((first_allowed-START).total_seconds()/300);r['segment_id']+='-future'
        r['future_at_offer']=bool(pd.Timestamp(r['delivery_from'])-pd.Timedelta(minutes=5)>=pd.Timestamp(r['offer_time']))
        rows.append(r)
    return pd.DataFrame(rows)

def run():
    seg=pd.read_parquet(RESULTS/'segments.parquet');seg=prospective_segments(seg);seg.to_parquet(RESULTS/'segments.parquet',index=False)
    rev=pd.read_parquet(RESULTS/'revisions.parquet')
    future=seg[seg.future_at_offer].copy();future['n']=future.period_to-future.period_from+1
    totals=future.groupby('offer_id').n.sum();rev['future_changed_intervals']=rev.offer_id.map(totals).fillna(0).astype(int)
    rev['past_changed_intervals']=rev.changed_intervals-rev.future_changed_intervals
    for col in ['peak_abs_le300_mw','max_increase_le300_mw','max_decrease_le300_mw','max_availability_increase_mw']:
        if col=='peak_abs_le300_mw':vals=(future.after_le300-future.before_le300).abs()
        elif col=='max_increase_le300_mw':vals=(future.after_le300-future.before_le300).clip(lower=0)
        elif col=='max_decrease_le300_mw':vals=(future.after_le300-future.before_le300).clip(upper=0)
        else:vals=(future.after_maxavail-future.before_maxavail).clip(lower=0)
        future[col]=vals;agg=future.groupby('offer_id')[col].min() if col=='max_decrease_le300_mw' else future.groupby('offer_id')[col].max()
        rev[col]=rev.offer_id.map(agg).fillna(0)
    rev.to_parquet(RESULTS/'revisions.parquet',index=False)
    borderline=rev[rev.offer_time.ge(SIGNAL)&rev.offer_time.lt(SPIKE)]
    borderline.to_csv(RESULTS/'timing_sensitivity.csv',index=False)
    # Compare accepted legal participants with the standing-map participant for every included unit.
    inv=load_table('inventory');h=load_table('headers');participants=h.groupby('DUID').PARTICIPANTID.agg(lambda x:'|'.join(sorted(set(x))))
    inv['event_participants']=inv.DUID.map(participants).fillna('No accepted offer')
    inv['participant_match']=inv.event_participants.eq(inv.PARTICIPANTID)
    save_table('inventory',inv)
    write_json(STATE/'enrichment.json',dict(prospective_rule='Delivery interval start >= offer timestamp; already running intervals excluded',timing_sensitive_revisions=len(borderline),participant_mismatches=inv.loc[~inv.participant_match&inv.event_participants.ne('No accepted offer'),['DUID','PARTICIPANTID','event_participants']].to_dict('records')))

if __name__=='__main__':run()
