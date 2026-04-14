"""Backward-compatible metadata exports.

`belgian_deduce.metadata` is the canonical module. This shim preserves the
historic `belgian_deduce.person` import path.
"""

from belgian_deduce.metadata import Address, DateLike, MetadataEntity, Person

__all__ = ["Address", "DateLike", "MetadataEntity", "Person"]
