# Contributing

Thanks for contributing to `belgian_deduce`.

Before you start:

* Open an issue first for larger features or data-source changes.
* Changes that belong in the shared framework should go to
  [`docdeid`](https://github.com/vmenger/docdeid).
* Rule changes should come with concrete Belgian clinical examples and an explanation
  of the expected precision or recall impact.

## Development Setup

```bash
pip install poetry
poetry install
```

Useful commands:

* `make format`
* `make lint`
* `make build-docs`
* `make clean`
* `pytest .`

## Pull Requests

Before opening a PR:

* Verify the test suite passes.
* Add or update tests for behavior changes.
* Run `make format` and `make lint`.
* Add a changelog entry when the user-facing behavior changes.
* Describe the motivation, impact, and any data assumptions in the PR body.

## Releases

* Create releases in this repository, not in the original `deduce` repository.
* Use the changelog as the release note source of truth.
* If docs or package publishing are automated, make sure they target
  `belgian_deduce` artifacts and not upstream `deduce` artifacts.
* PyPI publishing uses GitHub Actions Trusted Publishing via the `pypi`
  environment in `.github/workflows/build.yml`.
* Push a semantic version tag such as `v4.0.1` from the release commit on `main`
  to trigger the release workflow.
* The tag workflow publishes to PyPI first and only creates the GitHub release
  after a successful publish, using the matching `CHANGELOG.md` section as the
  release notes.
