# OctoPrint Git Backup

Automatically pushes OctoPrint backups to a remote Git repository every time a backup is created. Once you point it at a repo and authenticate once at the OS level, every new backup is committed and pushed — giving you a full, version-controlled history of your printer's configuration.

While GitHub is the primary target (with built-in setup helpers for the GitHub CLI), **any git remote works** — GitLab, Gitea, Bitbucket, self-hosted — as long as git on the host is authenticated.

[![Version](https://img.shields.io/badge/version-0.1.0-blue)](https://github.com/MauroDruwel/OctoPrint-Git-Backup/releases)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-green)](LICENSE)

## Features

- **Automatic** — listens for `plugin_backup_backup_created` and pushes without any manual steps
- **Version-controlled history** — every backup is a git commit; roll back any time
- **No stored credentials** — uses your OS-level GitHub CLI token (`gh auth login`), nothing is saved in the plugin
- **Optional auto-delete** — remove the local `.zip` after a successful push to save disk space
- **README-safe** — existing `README.md` in the repo is never overwritten
- **Live auth status panel** — shows git version, gh CLI auth state, and credential helper setup directly in the OctoPrint settings UI
- **One-click setup** — install git/gh CLI and run `gh auth login` from within the settings panel

## Requirements

- OctoPrint ≥ 1.6.0
- A git remote to push backups to

On **apt-based systems** (Raspberry Pi OS, Ubuntu, Debian — i.e. most OctoPrint installs), `git` and the GitHub CLI can be installed with one click directly from the plugin's settings panel. On other systems you'll need to install them yourself, but if you're running OctoPrint on a non-apt system you're probably already comfortable with that.

## Setup

### 1. Install the plugin

Install via the bundled [Plugin Manager](https://docs.octoprint.org/en/main/bundledplugins/pluginmanager.html) or manually using this URL:

```
https://github.com/MauroDruwel/OctoPrint-Git-Backup/archive/main.zip
```

### 2. Install git & authenticate

**On apt-based systems (Raspberry Pi OS, Ubuntu, Debian):** Everything can be done from the plugin's settings panel — install `git`, install the GitHub CLI (`gh`), and run `gh auth login` with one button each. The credential helper is configured automatically after login.

**On other systems:** Install `git` via your package manager, then authenticate using one of the methods below.

The plugin uses whatever git credentials are already configured at the OS level — nothing is stored in the plugin itself.

**GitHub via GitHub CLI:**
1. [Install `gh`](https://github.com/cli/cli#installation) if not already installed
2. Run `gh auth login` — follow the prompts
3. Run `gh auth setup-git` to wire the credential helper

**SSH key (works for any git host):**
Use an SSH URL (`git@github.com:user/repo.git`, `git@gitlab.com:user/repo.git`, etc.) and [set up an SSH key](https://docs.github.com/en/authentication/connecting-to-github-with-ssh) on the host. This works for GitHub, GitLab, Gitea, Bitbucket, or any self-hosted git server.

**Other HTTPS credentials:**
Configure git's credential helper on the host (e.g. `git config --global credential.helper store` or the OS keychain helper). Any HTTPS remote git can push to will work.

### 3. Configure the plugin

1. Go to **OctoPrint Settings → Git Backup Plugin**
2. Enter the HTTPS or SSH URL of your **private** GitHub repository
3. Optionally enable **"Delete local backup after a successful push"**
4. Click **Save**

That's it — the next backup you create will be pushed automatically.

## How it works

When a backup is created:
1. The plugin clones your repository into a temporary directory in `/tmp`
2. All files except `.git` and `README.md` are cleared
3. The backup `.zip` is extracted into the clone
4. Changes are committed (as `octoprint-backup[bot]`) and pushed to the remote
5. The temporary directory is cleaned up (and optionally the local `.zip` too)

## Configuration

| Setting | Description |
|---|---|
| Repository URL | HTTPS or SSH URL of your GitHub repository |
| Delete backup after push | If enabled, removes the local `.zip` after a successful push |

## Versioning

To release a new version:
1. Bump `version` in `pyproject.toml`
2. Commit and tag: `git tag v<version> && git push --tags`
3. Keep `extras/git_backup.md` metadata in sync

## License

[AGPL-3.0-or-later](LICENSE)
