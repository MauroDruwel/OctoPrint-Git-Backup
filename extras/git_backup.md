---
layout: plugin

id: git_backup
title: Git Backup Plugin
description: Automatically push OctoPrint backups to a remote Git repository after each backup is created.
authors:
- Mauro Druwel
license: MIT

date: 2026-05-14

homepage: https://github.com/MauroDruwel/OctoPrint-Git-Backup
source: https://github.com/MauroDruwel/OctoPrint-Git-Backup
archive: https://github.com/MauroDruwel/OctoPrint-Git-Backup/archive/main.zip

tags:
- backup
- git
- github
- configuration
- automation
- version control

screenshots: []

# attributes:
# #  - cloud  # plugin requires access to a cloud to function
# #  - commercial  # plugin has a commercial aspect
# #  - free-tier  # plugin has a free tier

compatibility:
  octoprint:
  - 1.6.0

  os:
  - linux
  - windows
  - macos
  - freebsd

  python: ">=3.7,<4"

---

Automatically pushes OctoPrint backups to a remote Git repository every time a backup is created. Once configured with a repo URL, every new backup is committed and pushed, keeping a full version-controlled history of your printer's configuration.

While GitHub is the primary target (with built-in GitHub CLI setup helpers), **any git remote works**, GitLab, Gitea, Bitbucket, self-hosted, as long as the host running OctoPrint is authenticated at the OS level (SSH key, credential manager, or `gh auth login` for GitHub).

## Features

- **Automatic**, listens for backup events and pushes without any manual steps
- **Version-controlled history**, every backup is a git commit; roll back any time
- **No stored credentials**, uses your OS-level GitHub CLI token (`gh auth login`), nothing is saved in the plugin
- **Optional auto-delete**, remove the local `.zip` after a successful push to save disk space
- **README-safe**, existing `README.md` in the repo is never overwritten by backup contents
- **Live auth status panel**, shows git/gh CLI status and credential helper setup in the OctoPrint settings UI
- **Guided GitHub CLI setup**, trigger `gh auth login` directly from the settings panel with device code flow
