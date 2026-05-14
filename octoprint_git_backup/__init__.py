# coding=utf-8
from __future__ import absolute_import

import os
import shutil
import subprocess
import tempfile
import threading
import zipfile
from datetime import datetime, timezone

import flask

import octoprint.plugin


class Git_backupPlugin(octoprint.plugin.SettingsPlugin,
                       octoprint.plugin.AssetPlugin,
                       octoprint.plugin.TemplatePlugin,
                       octoprint.plugin.EventHandlerPlugin,
                       octoprint.plugin.SimpleApiPlugin):

    def initialize(self):
        self._git_lock = threading.Lock()

    ##~~ SettingsPlugin mixin

    def get_settings_defaults(self):
        return {
            "repo_url": "",
            "delete_backup_after_push": False,
        }

    def get_settings_restricted_paths(self):
        # Repo URL may contain embedded credentials — restrict to admin only.
        return {"admin": [["repo_url"]]}

    ##~~ TemplatePlugin mixin

    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=True)
        ]

    ##~~ AssetPlugin mixin

    def get_assets(self):
        return {
            "js": ["js/git_backup.js"],
            "css": ["css/git_backup.css"],
            "less": ["less/git_backup.less"]
        }

    ##~~ EventHandlerPlugin mixin

    def on_event(self, event, payload):
        if event != "plugin_backup_backup_created":
            return

        payload = payload or {}
        backup_path = payload.get("path")
        backup_name = payload.get("name") or (
            os.path.basename(backup_path) if backup_path else None
        )

        if not backup_path or not os.path.exists(backup_path):
            self._logger.error("Git Backup: Backup file not found at %s", backup_path)
            return

        thread = threading.Thread(
            target=self._push_backup_to_git,
            args=(backup_path, backup_name),
            name="git_backup_push",
            daemon=False
        )
        thread.start()

    def _push_backup_to_git(self, backup_path, backup_name):
        if not self._git_lock.acquire(blocking=False):
            self._logger.warning(
                "Git Backup: A push is already in progress, skipping backup %s", backup_name
            )
            return

        tmp_dir = None
        try:
            repo_url = self._settings.get(["repo_url"])
            if not repo_url:
                self._logger.warning("Git Backup: No repo URL configured, skipping.")
                return

            delete_after = self._settings.get_boolean(["delete_backup_after_push"])
            tmp_dir = tempfile.mkdtemp(prefix="octoprint_git_backup_")

            # Prevent git from hanging on interactive prompts (credentials, host-key etc.)
            git_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

            # Clone repo
            self._logger.info("Git Backup: Cloning repository")
            result = subprocess.run(
                ["git", "clone", repo_url, tmp_dir],
                capture_output=True, text=True, timeout=120, env=git_env
            )
            if result.returncode != 0:
                self._logger.error("Git Backup: Clone failed:\n%s", result.stderr)
                return

            # Set commit identity locally in this clone (scoped to the temp dir only).
            for key, value in (("user.name", _GIT_AUTHOR_NAME), ("user.email", _GIT_AUTHOR_EMAIL)):
                result = subprocess.run(
                    ["git", "-C", tmp_dir, "config", key, value],
                    capture_output=True, text=True, timeout=10, env=git_env
                )
                if result.returncode != 0:
                    self._logger.error("Git Backup: git config %s failed:\n%s", key, result.stderr)
                    return

            # Clear existing files from clone (preserve .git and any manually maintained files)
            # so files deleted in OctoPrint are also removed from git on the next push.
            _PRESERVE = {".git"}
            for item in os.listdir(tmp_dir):
                if item in _PRESERVE or item.lower() == "readme.md":
                    continue
                item_path = os.path.join(tmp_dir, item)
                if os.path.islink(item_path) or os.path.isfile(item_path):
                    os.unlink(item_path)
                elif os.path.isdir(item_path):
                    shutil.rmtree(item_path)

            # Extract backup zip into the clone
            self._logger.info("Git Backup: Extracting backup %s", backup_name)
            with zipfile.ZipFile(backup_path, "r") as zf:
                zf.extractall(tmp_dir)

            # Stage, commit, push
            commit_message = "OctoPrint backup {}".format(
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            )

            result = subprocess.run(
                ["git", "-C", tmp_dir, "add", "-A"],
                capture_output=True, text=True, timeout=30, env=git_env
            )
            if result.returncode != 0:
                self._logger.error("Git Backup: git add failed:\n%s", result.stderr)
                return

            result = subprocess.run(
                ["git", "-C", tmp_dir, "commit", "-m", commit_message],
                capture_output=True, text=True, timeout=30, env=git_env
            )
            if result.returncode != 0:
                if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                    self._logger.info("Git Backup: Nothing changed since last backup, skipping push.")
                    return
                self._logger.error("Git Backup: git commit failed:\n%s", result.stderr)
                return

            # Use -u origin HEAD so this works for both first push (empty remote) and subsequent ones.
            result = subprocess.run(
                ["git", "-C", tmp_dir, "push", "-u", "origin", "HEAD"],
                capture_output=True, text=True, timeout=120, env=git_env
            )
            if result.returncode != 0:
                self._logger.error("Git Backup: git push failed:\n%s", result.stderr)
                return

            self._logger.info("Git Backup: Successfully pushed backup to repository")

            # Delete local backup only after a confirmed successful push
            if delete_after:
                helpers = self._plugin_manager.get_helpers("backup", "delete_backup")
                if helpers and "delete_backup" in helpers:
                    self._logger.info("Git Backup: Deleting local backup %s", backup_name)
                    helpers["delete_backup"](backup_name)
                else:
                    self._logger.warning("Git Backup: Could not get delete_backup helper")

        except subprocess.TimeoutExpired as e:
            self._logger.error("Git Backup: Git command timed out: %s", e)
        except Exception:
            self._logger.exception("Git Backup: Unexpected error during push")
        finally:
            self._git_lock.release()
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                self._logger.debug("Git Backup: Cleaned up temp dir %s", tmp_dir)

    ##~~ SimpleApiPlugin mixin

    def is_api_protected(self):
        return True

    def is_api_adminonly(self):
        return True

    def get_api_commands(self):
        return {}

    def on_api_get(self, request):
        # Suppress color codes and interactive prompts so output is clean.
        env = {
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "GH_PROMPT_DISABLED": "1",
            "NO_COLOR": "1",
            "CLICOLOR": "0",
            "TERM": "dumb",
        }
        result = {}

        # git
        try:
            r = subprocess.run(
                ["git", "--version"],
                capture_output=True, text=True, timeout=5, env=env
            )
            result["git_installed"] = r.returncode == 0
            result["git_version"] = r.stdout.strip() if r.returncode == 0 else None
        except Exception:
            result["git_installed"] = False
            result["git_version"] = None

        # gh CLI presence
        try:
            r = subprocess.run(
                ["gh", "--version"],
                capture_output=True, text=True, timeout=5, env=env
            )
            result["gh_installed"] = r.returncode == 0
        except Exception:
            result["gh_installed"] = False

        # gh auth — only if gh is present
        if result["gh_installed"]:
            try:
                r = subprocess.run(
                    ["gh", "auth", "status"],
                    capture_output=True, text=True, timeout=10, env=env
                )
                if r.returncode == 0:
                    result["gh_auth"] = True
                    # Fetch the authenticated username via the API (most reliable).
                    try:
                        r2 = subprocess.run(
                            ["gh", "api", "user", "--jq", ".login"],
                            capture_output=True, text=True, timeout=10, env=env
                        )
                        result["gh_username"] = r2.stdout.strip() if r2.returncode == 0 else None
                    except Exception:
                        result["gh_username"] = None
                else:
                    result["gh_auth"] = False
                    result["gh_username"] = None
            except subprocess.TimeoutExpired:
                result["gh_auth"] = False
                result["gh_username"] = None
        else:
            result["gh_auth"] = None  # None = not applicable (gh not installed)
            result["gh_username"] = None

        return flask.jsonify(result)

    ##~~ Softwareupdate hook

    def get_update_information(self):
        return {
            "git_backup": {
                "displayName": "Git Backup Plugin",
                "displayVersion": self._plugin_version,
                "type": "github_release",
                "user": "MauroDruwel",
                "repo": "OctoPrint-Git-Backup",
                "current": self._plugin_version,
                "pip": "https://github.com/MauroDruwel/OctoPrint-Git-Backup/archive/{target_version}.zip",
            }
        }


__plugin_name__ = "Git Backup Plugin"
__plugin_pythoncompat__ = ">=3,<4"

# GitHub App bot identity for commit attribution.
_GIT_AUTHOR_NAME = "octoprint-backup[bot]"
_GIT_AUTHOR_EMAIL = "284658542+octoprint-backup[bot]@users.noreply.github.com"


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = Git_backupPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
