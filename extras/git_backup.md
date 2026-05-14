---
layout: plugin

id: git_backup
title: OctoPrint-Git-Backup
description: Automatically push OctoPrint backups to a Git repository after each backup is created
authors:
- Mauro Druwel
license: AGPL-3.0-or-later

date: 2026-05-14

homepage: https://github.com/MauroDruwel/OctoPrint-Git-Backup
source: https://github.com/MauroDruwel/OctoPrint-Git-Backup
archive: https://github.com/MauroDruwel/OctoPrint-Git-Backup/archive/main.zip

# TODO
# Set this to true if your plugin uses the dependency_links setup parameter to include
# library versions not yet published on PyPi. SHOULD ONLY BE USED IF THERE IS NO OTHER OPTION!
#follow_dependency_links: false

# TODO
tags:
- backup
- git
- github
- configuration
- automation

# TODO
# When registering a plugin on plugins.octoprint.org, all screenshots should be uploaded not linked from external sites.
screenshots: []

# TODO
# featuredimage: url of a featured image for your plugin, /assets/img/...

# TODO
# You only need the following if your plugin requires specific OctoPrint versions or
# specific operating systems to function - you can safely remove the whole
# "compatibility" block if this is not the case.

compatibility:

  # List of compatible versions
  #
  # A single version number will be interpretated as a minimum version requirement,
  # e.g. "1.3.1" will show the plugin as compatible to OctoPrint versions 1.3.1 and up.
  # More sophisticated version requirements can be modelled too by using PEP440
  # compatible version specifiers.
  #
  # You can also remove the whole "octoprint" block. Removing it will default to all
  # OctoPrint versions being supported.

  octoprint:
  - 1.4.0

  # List of compatible operating systems
  #
  # Valid values:
  #
  # - windows
  # - linux
  # - macos
  # - freebsd
  #
  # There are also two OS groups defined that get expanded on usage:
  #
  # - posix: linux, macos and freebsd
  # - nix: linux and freebsd
  #
  # You can also remove the whole "os" block. Removing it will default to all
  # operating systems being supported.

  os:
  - linux
  - windows
  - macos
  - freebsd

  # Compatible Python version
  #
  # It is recommended to only support Python 3 for new plugins, in which case this should be ">=3,<4"
  # 
  # Plugins that wish to support both Python 2 and 3 should set it to ">=2.7,<4".
  #
  # Plugins that only support Python 2 will not be accepted into the plugin repository.

  python: ">=3,<4"

# TODO
# If any of the below attributes apply to your project, uncomment the corresponding lines. This is MANDATORY!

attributes:
#  - cloud  # if your plugin requires access to a cloud to function
#  - commercial  # if your plugin has a commercial aspect to it
#  - free-tier  # if your plugin has a free tier

---

Automatically pushes OctoPrint backups to a Git repository every time a backup is created. Once configured with a repo URL, each new OctoPrint backup is cloned, extracted, committed, and pushed — keeping a full version-controlled history of your printer's configuration.

## Features

- Listens for the `plugin_backup_backup_created` event and pushes automatically
- Configures via OctoPrint's Settings UI (repo URL, optional auto-delete of local backup after push)
- Uses your existing OS-level Git credentials (SSH key or `gh auth login`) — no passwords stored in the plugin
- Prevents concurrent pushes with a lock
- Cleans up temp files after each push
