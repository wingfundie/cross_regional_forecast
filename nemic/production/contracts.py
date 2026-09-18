"""Stable identities and serialization shared by adapters and models."""
import hashlib
import json
from pathlib import Path

CONNECTORS = {
    "VNI": ("VIC1-NSW1", "VIC1", "NSW1"),
    "QNI": ("NSW1-QLD1", "NSW1", "QLD1"),
    "Directlink": ("N-Q-MNSP1", "NSW1", "QLD1"),
    "Heywood": ("V-SA", "VIC1", "SA1"),
    "Murraylink": ("V-S-MNSP1", "VIC1", "SA1"),
    "Basslink": ("T-V-MNSP1", "TAS1", "VIC1"),
}
TARGETS = ("export", "import", "export_tight", "import_tight", "flow")
QUANTILES = (.025, .1, .5, .9, .975)
QCOLS = ("p02_5_mw", "p10_mw", "p50_mw", "p90_mw", "p97_5_mw")


def connector(value):
    for name, spec in CONNECTORS.items():
        if value in (name, spec[0]):
            return name
    raise ValueError(f"Unknown connector: {value}")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, default=str, allow_nan=False), encoding="utf-8")


def safe_path(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Artifact path escapes package")
    return path
