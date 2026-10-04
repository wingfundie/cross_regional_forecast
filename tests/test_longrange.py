import io
import zipfile

from nemic.longrange import extract_mtpasa


def mt_csv():
    return "\n".join([
        "C,SOLUTION,MTPASA,DUIDAVAILABILITY,3,2026/01/01,00:00:00",
        "I,MTPASA,DUIDAVAILABILITY,3,PUBLISH_DATETIME,DAY,REGIONID,DUID,PASAAVAILABILITY,PASAUNITSTATE,PASARECALLTIME,LATEST_OFFER_DATETIME,CARRYOVERSTATUS",
        "D,MTPASA,DUIDAVAILABILITY,3,2026/01/01 00:00:00,2026/01/05,NSW1,UNIT1,100,AVAILABLE,0,,",
        "D,MTPASA,DUIDAVAILABILITY,3,2026/01/01 00:00:00,2026/03/31,NSW1,UNIT1,80,AVAILABLE,0,,",
        "D,MTPASA,DUIDAVAILABILITY,3,2026/01/01 00:00:00,2026/05/01,NSW1,UNIT1,60,AVAILABLE,0,,",
    ])


def test_longrange_mt_cache_is_separate_and_bounded(tmp_path):
    raw = tmp_path / "raw" / "mtpasa"
    raw.mkdir(parents=True)
    with zipfile.ZipFile(raw / "a.zip", "w") as archive:
        archive.writestr("PUBLIC_MTPASA.csv", mt_csv())
    manifest = extract_mtpasa(tmp_path, horizon_days=90)
    assert manifest.parent.name == "mtpasa_90d"
    import pandas as pd
    frame = pd.read_parquet(manifest.parent / "a.parquet")
    assert len(frame) == 2
    assert frame.day.max().date().isoformat() == "2026-03-31"


def test_daily_extraction_keeps_the_1800_vintage(tmp_path):
    raw = tmp_path / "raw" / "mtpasa"; raw.mkdir(parents=True)
    def nested(capacity):
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as archive:
            archive.writestr("PUBLIC_MTPASA.csv", mt_csv().replace(",100,AVAILABLE", f",{capacity},AVAILABLE"))
        return payload.getvalue()
    with zipfile.ZipFile(raw / "a.zip", "w") as archive:
        archive.writestr("PUBLIC_MTPASA_202601011500_1.zip", nested(50))
        archive.writestr("PUBLIC_MTPASA_202601011800_2.zip", nested(120))
    manifest = extract_mtpasa(tmp_path, horizon_days=90)
    import pandas as pd
    frame = pd.read_parquet(manifest.parent / "a.parquet")
    assert frame.capacity_mw.max() == 120
