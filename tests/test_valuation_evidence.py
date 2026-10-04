import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nemic.valuation import baseline, evidence
from nemic.valuation.config import ROOT, cfg

REPORT = ROOT / 'reports/interregional_valuation_research_v2'


def _prices(n=288 * 3, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.date_range('2025-01-01 00:05', periods=n, freq='5min')
    base = rng.normal(80, 40, (n, 5))
    base[rng.random((n, 5)) < .02] += 5000
    base[rng.random((n, 5)) < .05] -= 150
    return pd.DataFrame(base, index=idx, columns=['NSW1', 'QLD1', 'SA1', 'TAS1', 'VIC1'])


def test_energy_scarcity_and_states_close_exactly():
    P = _prices()
    sp, st = baseline.spreads_and_states(P, baseline.V2_PAIRS)
    assert np.allclose(sp.spread, sp.energy + sp.scarcity)
    tot = st.groupby(['quarter', 'direction']).spread_contribution.sum()
    ref = sp.set_index(['quarter', 'direction']).spread
    assert np.allclose(tot.reindex(ref.index), ref)


def test_loss_congestion_two_by_two_closes():
    P = _prices()
    lam = pd.Series(np.random.default_rng(3).uniform(.9, 1.15, len(P)), index=P.index)
    ics = {a: pd.DataFrame({'MARGINALLOSS': lam, 'MWFLOW': 100.0}, index=P.index) for a in evidence.MAIN_ASSET.values()}
    out, _ = evidence.loss_congestion(P, ics)
    parts = out.energy_loss + out.scarcity_loss + out.energy_congestion + out.scarcity_congestion
    assert np.allclose(parts, out.spread)
    assert np.allclose(out.loss + out.congestion, out.spread)


def test_block_bootstrap_is_deterministic():
    P = _prices(288 * 20)
    a = evidence.bootstrap_quarters(P, 200, 7, 11)
    b = evidence.bootstrap_quarters(P, 200, 7, 11)
    pd.testing.assert_frame_equal(a, b)


def test_constraint_family_naming_heuristic():
    from nemic.valuation.mechanisms import constraint_family
    assert constraint_family('V>>V_NIL_2A_R') == ('thermal', 'system normal')
    assert constraint_family('N^^V_NIL_1') == ('voltage stability', 'system normal')
    assert constraint_family('V::N_HYSE_X') == ('transient stability', 'outage/other')
    assert constraint_family('NRM_NSW1_VIC1')[0] == 'negative residue management'


def test_report_template_placeholders_all_filled():
    ev = REPORT / 'evidence/headline_numbers.json'
    if not ev.exists():
        pytest.skip('evidence not built')
    numbers = json.loads(ev.read_text(encoding='utf-8'))
    tpl = (REPORT / 'research_report.template.md').read_text(encoding='utf-8')
    keys = set(re.findall(r'\{\{([a-zA-Z0-9_]+)\}\}', re.sub(r'\{\{include_v1[^}]*\}\}', '', tpl)))
    assert keys <= set(numbers), sorted(keys - set(numbers))


def test_katex_converter_fails_on_invalid_tex(tmp_path):
    node = shutil.which('node')
    if not node or not (REPORT / 'tools/node_modules/katex').exists():
        pytest.skip('node/katex not installed')
    good = tmp_path / 'ok.md'; good.write_text('Prices of $300 and $1,000; math $E=\\min(P,K)$.\n\n$$\nS=E+C\n$$\n', encoding='utf-8')
    r = subprocess.run([node, str(REPORT / 'convert_markdown.mjs'), str(good)], capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == 0 and json.loads(r.stderr.strip().splitlines()[-1])['math'] == 2 and '$300 and $1,000' in r.stdout
    bad = tmp_path / 'bad.md'; bad.write_text('$$\n\\frac{1}{\n$$\n', encoding='utf-8')
    assert subprocess.run([node, str(REPORT / 'convert_markdown.mjs'), str(bad)], capture_output=True).returncode != 0


def test_v1_regression_bit_exact():
    if not (ROOT / 'data/event_vni_2y/prices_5min.parquet').exists():
        pytest.skip('v1 archives not present')
    res = baseline.v1_regression()
    assert all(v['shape_equal'] and v['labels_equal'] and v['max_abs_diff'] == 0.0 for v in res.values()), res
