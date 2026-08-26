"""Multi-platform paper search providers and aggregation."""
from .aggregator import ALL_PLATFORMS, build_providers, search
from .base import SearchProvider

__all__ = ["ALL_PLATFORMS", "SearchProvider", "build_providers", "search"]
