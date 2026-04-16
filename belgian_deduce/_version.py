"""Version helpers for source-tree and installed-package execution."""

from __future__ import annotations

import re
from importlib import metadata
from pathlib import Path

_DISTRIBUTION_NAME = "belgian-deduce"
_PACKAGE_ROOT = Path(__file__).resolve().parent
_PYPROJECT_FILE = _PACKAGE_ROOT.parent / "pyproject.toml"
_POETRY_SECTION_PATTERN = re.compile(r"(?ms)^\[tool\.poetry\]\s*(.*?)(?:^\[|\Z)")
_VERSION_PATTERN = re.compile(r'(?m)^version\s*=\s*"([^"]+)"\s*$')


def _get_source_version() -> str | None:
    try:
        pyproject = _PYPROJECT_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None

    poetry_section = _POETRY_SECTION_PATTERN.search(pyproject)

    if poetry_section is None:
        return None

    version = _VERSION_PATTERN.search(poetry_section.group(1))

    if version is None:
        return None

    return version.group(1)


def get_package_version() -> str:
    source_version = _get_source_version()

    if source_version is not None:
        return source_version

    return metadata.version(_DISTRIBUTION_NAME)


__version__ = get_package_version()
