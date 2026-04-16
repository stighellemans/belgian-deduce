"""Helpers for generating build-time package cache artifacts."""

from __future__ import annotations

from pathlib import Path

from belgian_deduce._version import __version__
from belgian_deduce.deduce import Deduce, _LOOKUP_LIST_PATH
from belgian_deduce.lookup_structs import get_lookup_structs


def build_packaged_lookup_cache(
    lookup_data_path: Path = _LOOKUP_LIST_PATH,
    cache_path: Path = _LOOKUP_LIST_PATH,
    package_version: str = __version__,
) -> Path:
    """Build the packaged lookup cache into the package data directory."""

    tokenizer = Deduce._initialize_tokenizer(lookup_data_path)

    get_lookup_structs(
        lookup_path=lookup_data_path,
        cache_path=cache_path,
        tokenizer=tokenizer,
        package_version=package_version,
        build=True,
        save_cache=True,
    )

    return cache_path / "cache"
