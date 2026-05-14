# OctoPrint Git Backup 🖨️→🐙

![banner](assets/banner.png)

> Backs up your OctoPrint config to Git — automatically, every time.

[![GitHub release](https://img.shields.io/github/v/release/MauroDruwel/OctoPrint-Git-Backup?include_prereleases&label=release)](https://github.com/MauroDruwel/OctoPrint-Git-Backup/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-brightgreen)](LICENSE)
[![OctoPrint](https://img.shields.io/badge/OctoPrint-%E2%89%A51.6.0-blue)](https://octoprint.org)

Every backup you create gets committed and pushed to your repo. That's pretty much it. Your printer config is safe, versioned, and off-site.

Works with GitHub, GitLab, Gitea, Bitbucket, self-hosted — anything git can push to.

---

## Features

- 🔄 **Fully automatic** — hooks into OctoPrint's backup event, zero manual steps
- 🕓 **Full history** — every backup is a commit, roll back any time
- 🔐 **No stored credentials** — auth lives at the OS level, nothing in the plugin
- 🗑️ **Auto-delete** — optionally nuke the local `.zip` after a successful push
- 📄 **README-safe** — never overwrites an existing `README.md` in your repo
- 🟢 **Live status panel** — see git version, gh CLI auth, and credential helper state right in settings
- 📦 **One-click install** — install git and gh CLI without leaving OctoPrint *(apt-based systems only)*

---

## Requirements

- OctoPrint ≥ 1.6.0
- A git remote you can push to

On **Raspberry Pi OS / Ubuntu / Debian** (the usual suspects), `git` and the GitHub CLI can be installed straight from the plugin settings — no terminal needed. On other platforms you'll need to sort that yourself, but you probably already know what you're doing.

---

## Setup

### 1. Install the plugin

Via **OctoPrint Settings → Plugin Manager → Install from URL**:

```
https://github.com/MauroDruwel/OctoPrint-Git-Backup/archive/main.zip
```

### 2. Get git set up

**On apt-based systems** — open plugin settings and hit the install buttons. Done.

**Everywhere else** — install `git` via your package manager, then pick an auth method:

| Method | When to use |
|---|---|
| **GitHub CLI** (`gh auth login`) | GitHub HTTPS — easiest option, auto-configures the credential helper |
| **SSH key** | Any git host; use `git@host:user/repo.git` URL |
| **OS credential manager** | Any HTTPS remote; configure with `git config --global credential.helper <helper>` |

The plugin won't touch your credentials. If `git push` works in a terminal, it'll work here.

### 3. Configure

Go to **Settings → Git Backup Plugin**, paste your repo URL, optionally enable auto-delete, save. Next backup you create gets pushed.

---

## How it works

```
backup created
      │
      ▼
  clone repo → /tmp/octoprint_git_backup_*
      │
      ▼
  clear old files (keep .git + README.md)
      │
      ▼
  extract backup .zip
      │
      ▼
  git commit + push  ──→  your repo
      │
      ▼
  cleanup /tmp  (+ optionally delete .zip)
```

Commits are made as `octoprint-backup[bot]` so they're easy to spot in history.

---

## Configuration

| Setting | Description |
|---|---|
| Repository URL | HTTPS or SSH URL of your repo |
| Delete backup after push | Remove the local `.zip` after a successful push |

---

## Releasing

1. Bump `version` in `pyproject.toml`
2. `git tag v<version> && git push --tags`
3. Sync `extras/git_backup.md`

---

## License

[MIT](LICENSE)
