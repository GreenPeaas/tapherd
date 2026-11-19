# Contributing to TapHerd

Thanks for helping. TapHerd is a small project, so short, focused pull requests are easiest to review.

## Ground rules

- **Posting only.** Recipes and scheduling exist to post content to accounts the user owns. Contributions that automate engagement (likes, follows, comments, DMs, views), create or verify accounts, scrape other people's data, solve CAPTCHAs, spoof fingerprints, or evade detection will be closed. [Acceptable use](docs/ACCEPTABLE_USE.md)
- **No credentials.** TapHerd never asks for, stores, or logs passwords or tokens. Users type their own logins on the device.
- **No telemetry** in the free connector.
- **No overclaiming.** Say a recipe was "tested on [app version] on [date]", never "guaranteed".

## Set up

```sh
git clone https://github.com/asuopys/tapherd && cd tapherd
uv sync --locked
uv run pytest
```

Run the CLI from your checkout with `uv run tapherd …`. On macOS, if `uv sync` succeeds but the CLI raises `ModuleNotFoundError: No module named 'tapherd'`, set `UV_PROJECT_ENVIRONMENT=venv` and sync again: macOS can hide files inside `.venv`, and Python then skips the link to the source package ([uv issue](https://github.com/astral-sh/uv/issues/16977)).

Unit tests use a fake ADB, so you don't need a device to run them. Before opening a pull request, run:

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

CI runs these on macOS, Windows, and Linux with Python 3.11, 3.12, and 3.13.

## Code style

- Python 3.11+, type hints everywhere, `pathlib` for paths, and argument lists (never `shell=True`) for commands.
- Every error message tells the user the next command to run.
- Keep docs in plain English.

## Recipes

Write recipes against a test account. Mark them `status: unverified` until a real post completes, then record `tested_app_version`, `tested_on`, and `tested_device`, and add a line to `CHANGELOG.md`. [Recipe guide](docs/RECIPES.md)

## Reporting security issues

Please don't open a public issue. See [SECURITY.md](docs/SECURITY.md#report-a-vulnerability).
