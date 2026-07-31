# Repository Guidelines

## Project Structure & Module Organization

- `main.py`: AstrBot plugin registration and command entry point.
- `src/application/`: command orchestration, query/report services, and player/binding logic.
- `src/domain/`: domain models and enums (`PlayerStats`, `Report`, etc.).
- `src/infrastructure/`: HTTP clients, parsers, repositories, gateways, and third-party API clients.
- `src/settings/`: configuration constants, storage, and message templates.
- `src/tasks/`: scheduled tasks (e.g., daily tank data sync).
- `tests/`: pytest suite mirroring use cases and command flows.
- `resources/static/`: Jinja2 report templates, fonts, and static tank data.
- `metadata.yaml` / `_conf_schema.json`: plugin metadata and config schema.

Runtime data lives in `data/plugin_data/astrbot_plugin_wot/data/`; generated reports are cached under `data/temp/astrbot_plugin_wot/report/`.

## Build, Test, and Development Commands

This plugin runs inside AstrBot and has no standalone build. Install dependencies with:

```bash
pip install -r requirements.txt
```

Run the test suite from the AstrBot repository root (tests import via `data.plugins.astrbot_plugin_wot.*`):

```bash
python -m pytest data/plugins/astrbot_plugin_wot/tests
```

Run one file or test case with:

```bash
python -m pytest data/plugins/astrbot_plugin_wot/tests/test_plugin_commands.py -k test_name
```

## Coding Style & Naming Conventions

- Python 3.10+, 4-space indentation, and type hints (`str | None`); use `from __future__ import annotations` where convenient.
- `snake_case` for functions/variables, `CamelCase` for classes, `snake_case.py` for modules.
- Import order: standard library, third-party, then `data.plugins.astrbot_plugin_wot.*`.
- Docstrings and user-facing messages may be written in Chinese; keep explanations concise.
- No linter or formatter is configured — match the surrounding style and keep diffs focused.

## Testing Guidelines

- Tests use `pytest` with mocks (`AsyncMock`, `MagicMock`, `DummyEvent`); never hit live APIs.
- Name test files `test_<subject>.py` and test functions/classes `test_*`.
- Cover command parsing, cache behavior, and report rendering size/use cases.

## Commit & Pull Request Guidelines

- Use Conventional Commits with a Chinese subject, and a scope when helpful: `feat:`, `fix:`, `refactor:`, `chore:` (e.g., `fix(plugin/wot): 修复命令重复触发问题`).
- Make one logical change per commit; bump `version` in `metadata.yaml` for user-visible changes.
- In PRs, describe the change, affected commands, and how it was tested; link related issues and update `README.md` when commands or behavior change.
