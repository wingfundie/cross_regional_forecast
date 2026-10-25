"""Entrypoint for isolated conditional-regime research and cached reporting."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "packages/nemic-regimes/src"))

if __name__ == "__main__":
    from nemic.experiments.conditional_regimes.campaign import main
    main()
