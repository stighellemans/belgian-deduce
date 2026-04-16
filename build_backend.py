"""Custom PEP 517 backend that primes packaged lookup cache before wheel builds."""

from __future__ import annotations

from typing import Any


def _get_poetry_api() -> Any:
    from poetry.core.masonry import api

    return api


def _build_packaged_lookup_cache() -> None:
    from belgian_deduce.build_cache import build_packaged_lookup_cache

    build_packaged_lookup_cache()


def build_wheel(
    wheel_directory: str,
    config_settings: dict[str, Any] | None = None,
    metadata_directory: str | None = None,
) -> str:
    _build_packaged_lookup_cache()
    return _get_poetry_api().build_wheel(
        wheel_directory,
        config_settings=config_settings,
        metadata_directory=metadata_directory,
    )


def build_sdist(
    sdist_directory: str, config_settings: dict[str, Any] | None = None
) -> str:
    return _get_poetry_api().build_sdist(
        sdist_directory, config_settings=config_settings
    )


def get_requires_for_build_wheel(
    config_settings: dict[str, Any] | None = None,
) -> list[str]:
    return _get_poetry_api().get_requires_for_build_wheel(
        config_settings=config_settings
    )


def get_requires_for_build_sdist(
    config_settings: dict[str, Any] | None = None,
) -> list[str]:
    return _get_poetry_api().get_requires_for_build_sdist(
        config_settings=config_settings
    )


def prepare_metadata_for_build_wheel(
    metadata_directory: str, config_settings: dict[str, Any] | None = None
) -> str:
    return _get_poetry_api().prepare_metadata_for_build_wheel(
        metadata_directory, config_settings=config_settings
    )


def build_editable(
    wheel_directory: str,
    config_settings: dict[str, Any] | None = None,
    metadata_directory: str | None = None,
) -> str:
    _build_packaged_lookup_cache()
    return _get_poetry_api().build_editable(
        wheel_directory,
        config_settings=config_settings,
        metadata_directory=metadata_directory,
    )


def get_requires_for_build_editable(
    config_settings: dict[str, Any] | None = None,
) -> list[str]:
    return _get_poetry_api().get_requires_for_build_editable(
        config_settings=config_settings
    )


def prepare_metadata_for_build_editable(
    metadata_directory: str, config_settings: dict[str, Any] | None = None
) -> str:
    return _get_poetry_api().prepare_metadata_for_build_editable(
        metadata_directory, config_settings=config_settings
    )
