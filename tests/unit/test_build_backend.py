from pathlib import Path
import re

import build_backend


def test_build_wheel_builds_cache_before_delegating(monkeypatch):
    calls = []

    class PoetryApi:
        @staticmethod
        def build_wheel(
            wheel_directory, config_settings=None, metadata_directory=None
        ):
            calls.append(
                (
                    "build_wheel",
                    wheel_directory,
                    config_settings,
                    metadata_directory,
                )
            )
            return "belgian_deduce-4.0.0-py3-none-any.whl"

    monkeypatch.setattr(
        build_backend, "_build_packaged_lookup_cache", lambda: calls.append("cache")
    )
    monkeypatch.setattr(build_backend, "_get_poetry_api", lambda: PoetryApi)

    wheel = build_backend.build_wheel(
        "dist", config_settings={"opt": "1"}, metadata_directory="metadata"
    )

    assert wheel == "belgian_deduce-4.0.0-py3-none-any.whl"
    assert calls == [
        "cache",
        ("build_wheel", "dist", {"opt": "1"}, "metadata"),
    ]


def test_pyproject_includes_build_backend_in_sdist() -> None:
    pyproject = (
        Path(__file__).resolve().parents[2] / "pyproject.toml"
    ).read_text(encoding="utf-8")

    assert re.search(
        r'\{\s*path\s*=\s*"build_backend\.py"\s*,\s*format\s*=\s*\[\s*"sdist"\s*\]\s*\}',
        pyproject,
    )
