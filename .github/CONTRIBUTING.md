# Contributing to Server Mirror

Bug reports, focused fixes, tests, and documentation improvements are welcome.

## Local setup

Use Python 3.10 or newer, fork or clone this repository, and create a virtual environment:

```bash
python -m venv .venv
```

Activate the virtual environment before installing, or use its Python executable directly. On Windows that executable is `.venv\Scripts\python.exe`; on Linux/macOS it is `.venv/bin/python`.

```bash
python -m pip install -r requirements/dev.txt
```

Create a descriptive branch and run these checks before opening a pull request:

```bash
python -m ruff check .
python -m ruff format --check .
python -m unittest discover -s tests -v
python -m pip_audit -r requirements/runtime.txt
```

Use `python -m ruff format .` to apply formatting.

## Changes and tests

- Keep code, comments, documentation, and user-facing messages in English.
- Include a regression test when fixing copy logic or permission handling.
- Keep unit tests offline. Do not add tokens or real Discord credentials to fixtures.
- Preserve preview mode, explicit confirmation, ID-based mappings, and immediate stopping for critical failures. Recoverable omissions must disclose their consequences and require confirmation in copy mode.
- Document changes to supported channel types and copy limitations in the README.
- Add user-visible changes under `[Unreleased]` in the changelog.
- Describe the problem, resulting behavior, and validation in your pull request.

Live testing must use authorized, disposable servers and an explicitly confirmed copy. Never test destructive operations against a production server.

## Automation

- **Python CI:** lint and formatting, Linux tests on Python 3.10–3.14, and Windows tests on Python 3.14.
- **Dependency audit:** checks runtime dependencies on pushes, pull requests, manual runs, and a weekly schedule.
- **Dependabot:** weekly pip and GitHub Actions update checks.
- **Inactive discussions:** issues are marked stale after 60 days and closed after another 30; pull requests are marked after 90 days and are not automatically closed. The labels `security`, `bug`, `pinned`, and `keep-open` exempt issues and pull requests.

Scheduled workflows and Dependabot configuration must be on the repository's default branch. GitHub Actions must be enabled.

For sensitive findings, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.
