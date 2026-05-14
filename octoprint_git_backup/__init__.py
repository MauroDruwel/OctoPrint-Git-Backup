# coding=utf-8
from __future__ import absolute_import

import os
import re
import select
import shutil
import subprocess
import tempfile
import threading
import time
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
        self._auth_proc = None

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
            dict(type="settings", custom_bindings=False)
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
            # Use gh as the credential helper so HTTPS repos authenticate via the stored gh token.
            git_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
            git_base = ["git", "-c", "credential.helper=!gh auth git-credential"]

            # Clone repo
            self._logger.info("Git Backup: Cloning repository")
            result = subprocess.run(
                git_base + ["clone", repo_url, tmp_dir],
                capture_output=True, text=True, timeout=120, env=git_env
            )
            if result.returncode != 0:
                self._logger.error("Git Backup: Clone failed:\n%s", result.stderr)
                return

            # Set commit identity locally in this clone (scoped to the temp dir only).
            for key, value in (("user.name", _GIT_AUTHOR_NAME), ("user.email", _GIT_AUTHOR_EMAIL)):
                result = subprocess.run(
                    git_base + ["-C", tmp_dir, "config", key, value],
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
                git_base + ["-C", tmp_dir, "add", "-A"],
                capture_output=True, text=True, timeout=30, env=git_env
            )
            if result.returncode != 0:
                self._logger.error("Git Backup: git add failed:\n%s", result.stderr)
                return

            result = subprocess.run(
                git_base + ["-C", tmp_dir, "commit", "-m", commit_message],
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
                git_base + ["-C", tmp_dir, "push", "-u", "origin", "HEAD"],
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
        return {
            "install_git": [],
            "install_gh": [],
            "start_auth_login": [],
            "check_repo": ["url"],
        }

    def on_api_command(self, command, data):
        if command == "install_git":
            return self._api_apt_install("git")
        elif command == "install_gh":
            return self._api_install_gh()
        elif command == "start_auth_login":
            return self._api_start_auth_login()
        elif command == "check_repo":
            return self._api_check_repo(data.get("url", ""))

    def _sudo(self, cmd):
        """Prepend sudo only when not already root."""
        return cmd if os.getuid() == 0 else ["sudo"] + cmd

    def _api_check_repo(self, url):
        nwo = _extract_nwo(url)
        if not nwo:
            return flask.jsonify({"nwo": None, "is_private": None})
        env = {
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0", "GH_PROMPT_DISABLED": "1",
            "NO_COLOR": "1", "CLICOLOR": "0", "TERM": "dumb",
        }
        try:
            r = subprocess.run(
                ["gh", "repo", "view", nwo, "--json", "isPrivate", "--jq", ".isPrivate"],
                capture_output=True, text=True, timeout=10, env=env
            )
            if r.returncode == 0:
                return flask.jsonify({"nwo": nwo, "is_private": r.stdout.strip() == "true"})
            return flask.jsonify({"nwo": nwo, "is_private": None, "error": "not_found"})
        except Exception as e:
            return flask.jsonify({"nwo": nwo, "is_private": None, "error": str(e)})

    def _api_apt_install(self, package):
        env = {**os.environ, "DEBIAN_FRONTEND": "noninteractive"}
        try:
            r = subprocess.run(
                self._sudo(["apt-get", "install", "-y", package]),
                capture_output=True, text=True, timeout=180, env=env
            )
            if r.returncode == 0:
                return flask.jsonify({"success": True})
            self._logger.warning("apt-get install %s failed:\n%s", package, r.stderr)
            return flask.jsonify({"success": False, "stderr": r.stderr[:400]})
        except subprocess.TimeoutExpired:
            return flask.jsonify({"success": False, "stderr": "Installation timed out."})
        except Exception as e:
            return flask.jsonify({"success": False, "stderr": str(e)})

    def _api_install_gh(self):
        """Install GitHub CLI: try plain apt first, fall back to official repo method."""
        import urllib.request

        env = {**os.environ, "DEBIAN_FRONTEND": "noninteractive"}

        def run(cmd, timeout=60, input=None):
            r = subprocess.run(
                self._sudo(cmd),
                capture_output=True, text=True, timeout=timeout,
                env=env, input=input
            )
            if r.returncode != 0:
                raise RuntimeError(r.stderr.strip() or r.stdout.strip())
            return r.stdout.strip()

        try:
            # Fast path: gh is already in the default repos (some distros have it).
            try:
                run(["apt-get", "install", "-y", "gh"], timeout=120)
                return flask.jsonify({"success": True})
            except Exception:
                pass  # Not in default repos — fall through to official method.

            # Official method: add GitHub CLI apt repo, then install.
            arch = subprocess.run(
                ["dpkg", "--print-architecture"],
                capture_output=True, text=True, timeout=5
            ).stdout.strip()

            keyring_path = "/etc/apt/keyrings/githubcli-archive-keyring.gpg"
            sources_path = "/etc/apt/sources.list.d/github-cli.list"

            run(["mkdir", "-p", "-m", "755", "/etc/apt/keyrings"])

            keyring_data = urllib.request.urlopen(
                "https://cli.github.com/packages/githubcli-archive-keyring.gpg",
                timeout=30
            ).read()
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".gpg")
            try:
                tmp.write(keyring_data)
                tmp.flush()
                tmp.close()
                run(["cp", tmp.name, keyring_path])
                run(["chmod", "go+r", keyring_path])
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass

            run(["mkdir", "-p", "-m", "755", "/etc/apt/sources.list.d"])
            source_line = (
                "deb [arch={arch} signed-by={keyring}] "
                "https://cli.github.com/packages stable main\n"
            ).format(arch=arch, keyring=keyring_path)
            run(["tee", sources_path], input=source_line)
            run(["apt-get", "update", "-q"], timeout=120)

            run(["apt-get", "install", "-y", "gh"], timeout=180)
            return flask.jsonify({"success": True})

        except subprocess.TimeoutExpired:
            return flask.jsonify({"success": False, "stderr": "Installation timed out."})
        except Exception as e:
            self._logger.warning("gh install failed: %s", e)
            return flask.jsonify({"success": False, "stderr": str(e)[:400]})

    def _api_start_auth_login(self):
        # Kill any lingering previous auth process.
        if self._auth_proc and self._auth_proc.poll() is None:
            self._auth_proc.terminate()
            self._auth_proc = None

        env = {
            **os.environ,
            "NO_COLOR": "1", "CLICOLOR": "0", "TERM": "dumb",
            "GIT_TERMINAL_PROMPT": "0",
        }
        try:
            proc = subprocess.Popen(
                ["gh", "auth", "login", "-h", "github.com", "-p", "https", "--web"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                env=env,
            )
        except FileNotFoundError:
            return flask.jsonify({"success": False, "error": "gh_not_found"})

        # Read output line by line until we find the XXXX-XXXX device code.
        code = None
        deadline = time.time() + 15
        while time.time() < deadline:
            ready, _, _ = select.select([proc.stdout], [], [], 0.3)
            if ready:
                line = proc.stdout.readline()
                if not line:
                    break
                m = re.search(r'([A-Z0-9]{4}-[A-Z0-9]{4})', line)
                if m:
                    code = m.group(1)
                    break
            if proc.poll() is not None:
                break

        if code:
            self._auth_proc = proc
            return flask.jsonify({
                "success": True,
                "code": code,
                "url": "https://github.com/login/device",
            })

        try:
            proc.terminate()
        except Exception:
            pass
        return flask.jsonify({"success": False, "error": "no_code"})

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

# Regex to extract "owner/repo" from HTTPS or SSH GitHub URLs.
_NWO_RE = re.compile(
    r'github\.com[:/](?P<nwo>[^/]+/[^/]+?)(?:\.git)?$'
)


def _extract_nwo(url):
    """Return 'owner/repo' from a GitHub URL, or None if not parseable."""
    m = _NWO_RE.search(url.strip())
    return m.group("nwo") if m else None


def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = Git_backupPlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
