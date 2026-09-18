"""Manual campaign continuation with durable stages and no implicit promotion."""
import json
import pandas as pd
from pathlib import Path

from .tracking import atomic
from .tracking import ReadyForResume
from .sources import inventory,acquire,coverage_audit


def run(ledger):
    """Resume completed source jobs; stop on exhausted resources, never invent results."""
    from .coal import prepare
    from .weather import acquire_weather
    from .modelling import build_tables_parallel,fit_table
    from .indexes import prepare_indexes
    from .reports import render
    ledger.reconcile()
    ledger.record('methodology','completed','Methodology frozen before campaign continuation',
                  [ledger.methodology,ledger.root/'methodology/feature_research.md',ledger.root/'methodology/selection_review.md'])
    try:
        inventory(ledger)
        summary=acquire(ledger,'ARCHIVE',0)
        source_status=json.loads(summary.read_text())
        coverage=coverage_audit(ledger)
        if coverage['historical_pasa_days']<130 or coverage['historical_mt_days']<130:
            raise RuntimeError('Available original-report archives did not establish 130 matched historical days; inspect acquisition_summary.json')
        prepare(ledger)
        prepare_indexes(ledger,resume=True)
        dates=coverage['historical_pasa_dates']
        # Include the previous UTC cycle for the first local-NEM forecast origin.
        for day in pd.date_range(pd.Timestamp(dates[0])-pd.Timedelta(days=1),dates[-1],freq='D',tz='UTC'):
            acquire_weather(ledger,day)
        names=['VNI','QNI']
        paths=build_tables_parallel(ledger.c,names,None,2)
        # Connector campaigns are intentionally sequential: VNI must complete
        # before any QNI feature reduction, training or assessment begins.
        by_name={path.parent.name:path for path in map(Path,paths)}
        for name in names:fit_table(ledger,by_name[name])
        from .assessment import assess
        assess(ledger)
        # Acceptance is deliberately separate from successful fitting.
        ledger.record('assessment','ready','Point fits completed; full-horizon, incident-risk, source-vintage and power gates still required')
    except ReadyForResume as exc:
        note=ledger.root/'logs/campaign_ready.json'
        atomic(note,json.dumps({'type':type(exc).__name__,'detail':str(exc)},indent=2))
        ledger.record('campaign/continuation','ready',str(exc))
    except Exception as exc:
        note=ledger.root/'logs/campaign_failure.json'
        atomic(note,json.dumps({'type':type(exc).__name__,'error':str(exc)},indent=2))
        ledger.record('campaign/continuation','failed',str(exc))
        raise
    finally:
        render(ledger)
