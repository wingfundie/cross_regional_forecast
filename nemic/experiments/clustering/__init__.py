"""Isolated QNI/VNI clustering research campaign.

The package deliberately sits below :mod:`nemic.experiments` so adding it does
not alter the legacy experiment code manifest or invalidate existing results.
"""

from .config import DEFAULT_CONFIG, load_config

__all__ = ["DEFAULT_CONFIG", "load_config"]

