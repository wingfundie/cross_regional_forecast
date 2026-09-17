"""Portable, opt-in interconnector forecasting scaffold. No import-time I/O."""

from .registry import Registry
from .pipeline import forecast

__all__ = ["Registry", "forecast"]
