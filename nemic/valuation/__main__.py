"""CLI: python -m nemic.valuation <stage> [<stage> ...] | all"""
import importlib
import json
import sys

STAGES = [
    ('acquire', 'nemic.valuation.acquire', 'run'),
    ('panel', 'nemic.valuation.panel', 'run'),
    ('baseline', 'nemic.valuation.baseline', 'run'),
    ('settlement', 'nemic.valuation.settlement', 'run'),
    ('evidence', 'nemic.valuation.evidence', 'run'),
    ('market', 'nemic.valuation.market', 'run'),
    ('mechanisms', 'nemic.valuation.mechanisms', 'run'),
    ('valuation', 'nemic.valuation.valuation_tests', 'run'),
]


def main(argv):
    names = [s[0] for s in STAGES]
    wanted = names if argv == ['all'] else argv
    unknown = set(wanted) - set(names)
    if not wanted or unknown:
        raise SystemExit(f'usage: python -m nemic.valuation <{"|".join(names)}|all>; unknown: {sorted(unknown)}')
    import subprocess
    for name, mod, fn in STAGES:
        if name in wanted:
            print(f'== stage {name}', flush=True)
            if len(wanted) > 1:  # isolate memory: one process per stage
                code = f"import json,importlib;print(json.dumps(getattr(importlib.import_module('{mod}'),'{fn}')(),default=str,ensure_ascii=True)[:4000],flush=True)"
                r = subprocess.run([sys.executable, '-c', code])
                if r.returncode:
                    raise SystemExit(f'stage {name} failed with exit code {r.returncode}')
            else:
                print(json.dumps(getattr(importlib.import_module(mod), fn)(), default=str, ensure_ascii=True)[:4000], flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
