# Copilot Instructions

## Project Overview

This is an **OctoPrint plugin** (`OctoPrint-Git-Backup`) that backs up OctoPrint configuration/files to a Git repository. It follows the standard OctoPrint plugin skeleton structure.

- **Language**: Python 3 (>=3.7, <4) backend; KnockoutJS + LESS frontend
- **License**: AGPL-3.0-or-later
- **Entry point**: `octoprint_git_backup` package (registered as `git_backup` in `pyproject.toml`)

## Build & Install Commands

All tasks use [go-task](https://taskfile.dev) (`task`):

```bash
# Install into current venv (editable + dev deps)
task install
# equivalent: python -m pip install -e .[develop]

# Build sdist + wheel
task build

# Build sdist only / wheel only
task build-sdist
task build-wheel
```

## Architecture

The entire plugin logic lives in `octoprint_git_backup/__init__.py`. OctoPrint plugins are registered through Python entry points and loaded by the OctoPrint host process — there is no standalone main entry point.

**Plugin class** `Git_backupPlugin` inherits from OctoPrint mixins:
- `SettingsPlugin` — settings defaults via `get_settings_defaults()`; settings accessed at runtime via `self._settings`
- `AssetPlugin` — declares JS/CSS/LESS assets in `get_assets()`; assets are auto-included in the OctoPrint UI
- `TemplatePlugin` — Jinja2 templates in `octoprint_git_backup/templates/`

**Frontend** uses KnockoutJS. The ViewModel is registered via:
```js
OCTOPRINT_VIEWMODELS.push({ construct: ..., dependencies: [...], elements: [...] });
```

**Plugin hooks** (e.g., software update) are wired in `__plugin_load__()` via `__plugin_hooks__`.

**Key control properties** at module level:
- `__plugin_name__` — display name
- `__plugin_pythoncompat__` — Python version constraint
- `__plugin_implementation__` — plugin instance (set in `__plugin_load__`)
- `__plugin_hooks__` — dict mapping hook names to handlers

## Translations (i18n)

Translations use `pybabel` + Babel. Workflow via Taskfile:

```bash
task babel-extract      # update .pot file from source
task babel-new -- de    # create a new locale (e.g. German)
task babel-refresh      # re-extract + update all locales
task babel-compile      # compile .po → .mo
task babel-bundle       # copy compiled translations into plugin package
```

Locales to include must be listed in `Taskfile.yml` under `env.LOCALES`.

Translation strings in Python use `gettext`/`ngettext`; in JS files use `gettext`/`ngettext`; in Jinja2 templates use the `trycatch` extension pattern.

## OctoPrint Documentation Reference

OctoPrint's plugin API is not widely covered in general AI training data. **Always consult the official docs** when working on plugin features:

- **Plugin development guide** (mixins, hooks, lifecycle, distributing): https://docs.octoprint.org/en/main/plugins/gettingstarted.html#growing-up-how-to-make-it-distributable
- **Full plugin API reference**: https://docs.octoprint.org/en/main/plugins/

## Building on the Backup Plugin

This plugin integrates with OctoPrint's bundled Backup plugin to trigger and manage backups, then push them to Git. Docs: https://docs.octoprint.org/en/main/bundledplugins/backup.html

**Triggering a backup programmatically** via the backup plugin's exported helper:
```python
helpers = self._plugin_manager.get_helpers("backup", "create_backup")
if helpers and "create_backup" in helpers:
    helpers["create_backup"](exclude=["timelapse", "uploads"], filename="my_backup.zip")
```

**Deleting a backup** via helper:
```python
helpers = self._plugin_manager.get_helpers("backup", "delete_backup")
if helpers and "delete_backup" in helpers:
    helpers["delete_backup"]("my_backup.zip")
```

**Reacting to backup lifecycle events** via hooks in `__plugin_hooks__`:

| Hook | When |
|------|------|
| `octoprint.plugin.backup.before_backup` | Right before a backup is created |
| `octoprint.plugin.backup.after_backup` | After creation (receives `error=True` on failure) |
| `octoprint.plugin.backup.before_restore` | Right before a restore |
| `octoprint.plugin.backup.after_restore` | After restore (receives `error=True` on failure) |
| `octoprint.plugin.backup.additional_excludes` | Provide paths to exclude from backup |

**Event**: `plugin_backup_backup_created` — fired when a backup is successfully created. Payload: `name`, `path`, `excludes`.

> **Note**: The backup plugin's helpers and `after_backup`/`before_backup` hooks require OctoPrint ≥ 1.6.0 (helpers) / ≥ 1.9.0 (hooks). Guard with `if helpers and "create_backup" in helpers` to stay compatible with older versions.

## Versioning

Version is defined **once** in `pyproject.toml` (`version = "0.1.0"`). When releasing:

1. Bump `version` in `pyproject.toml`
2. Create a matching git tag: `git tag v<version> && git push origin v<version>`

OctoPrint's Software Update plugin uses GitHub releases/tags to notify users of updates (wired via `get_update_information()` in `__init__.py` — no code change needed there).

Keep `extras/git_backup.md` (the plugin registry listing) in sync with `pyproject.toml` — bump its `version:` field too when releasing.



- **Asset filenames** must match the plugin identifier: `git_backup.js`, `git_backup.css`, `git_backup.less`
- **Template bindings**: UI elements are bound by ID convention `#settings_plugin_git_backup`, `#tab_plugin_git_backup`, etc.
- **Settings access in Python**: use `self._settings.get(["key"])` / `self._settings.set(["key"], value)`
- **OctoPrint logger**: use `self._logger` (injected automatically by the framework)
- **Plugin identifier** (used in URLs, IDs): `git_backup` (underscore, not hyphen)
- LESS is the source of truth for styles; the compiled CSS in `static/css/` is the output
- The `extras/git_backup.md` file is the plugin registry listing for [plugins.octoprint.org](https://plugins.octoprint.org) — keep its metadata in sync with `pyproject.toml`
- **Plugin init state**: use `initialize()` (not `__init__`) for setting up instance state like locks — this is the OctoPrint-approved lifecycle method
- **Git operations**: use `subprocess.run` directly (GitPython was evaluated and rejected — it's itself a subprocess wrapper). Always set `GIT_TERMINAL_PROMPT=0` in the env to prevent git from hanging on interactive credential/host-key prompts. Always set `timeout=` on subprocess calls
- **Auth**: no credentials are stored in the plugin. Users authenticate once at the OS level via `gh auth login` (GitHub CLI) or SSH key. The plugin's settings template documents this with links
- **CLI backup limitation**: `plugin_backup_backup_created` events are not fired for backups created via the OctoPrint CLI (`octoprint plugins backup:backup`), only for UI/API-triggered backups

