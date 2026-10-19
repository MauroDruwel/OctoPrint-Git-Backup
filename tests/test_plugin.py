import ast
import os
import re
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Ensure mock modules are configured even if run via unittest directly
if "flask" not in sys.modules:
    flask_mock = MagicMock()
    flask_mock.jsonify = lambda x: x
    sys.modules["flask"] = flask_mock

if "octoprint" not in sys.modules or not hasattr(sys.modules["octoprint"], "__path__"):
    octoprint_mod = types.ModuleType("octoprint")
    octoprint_mod.__path__ = []

    plugin_mod = types.ModuleType("octoprint.plugin")

    class SettingsPlugin:
        pass

    class AssetPlugin:
        pass

    class TemplatePlugin:
        pass

    class EventHandlerPlugin:
        pass

    class SimpleApiPlugin:
        pass

    plugin_mod.SettingsPlugin = SettingsPlugin
    plugin_mod.AssetPlugin = AssetPlugin
    plugin_mod.TemplatePlugin = TemplatePlugin
    plugin_mod.EventHandlerPlugin = EventHandlerPlugin
    plugin_mod.SimpleApiPlugin = SimpleApiPlugin

    octoprint_mod.plugin = plugin_mod
    sys.modules["octoprint"] = octoprint_mod
    sys.modules["octoprint.plugin"] = plugin_mod

import octoprint_git_backup
from octoprint_git_backup import (
    Git_backupPlugin,
    _extract_nwo,
    __plugin_name__,
    __plugin_version__,
    __plugin_pythoncompat__,
)


class TestPluginMetadataAndHeaders(unittest.TestCase):
    def test_plugin_metadata(self):
        self.assertEqual(__plugin_version__, "0.1.0")
        self.assertEqual(__plugin_pythoncompat__, ">=3.7,<4")
        self.assertEqual(__plugin_name__, "Git Backup Plugin")

    def test_no_python2_headers(self):
        init_file = os.path.join(REPO_ROOT, "octoprint_git_backup", "__init__.py")
        with open(init_file, "r", encoding="utf-8") as f:
            lines = [f.readline() for _ in range(15)]
        for line in lines:
            self.assertNotIn("coding=utf-8", line)
            self.assertNotIn("from __future__ import", line)

    def test_manifest_python_compat(self):
        # pyproject.toml
        pyproject_file = os.path.join(REPO_ROOT, "pyproject.toml")
        with open(pyproject_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('requires-python = ">=3.7,<4"', content)

        # extras/git_backup.md
        extras_file = os.path.join(REPO_ROOT, "extras", "git_backup.md")
        with open(extras_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('python: ">=3.7,<4"', content)

        # plugins.octoprint.org manifest if accessible
        official_manifest = os.path.join(
            os.path.dirname(REPO_ROOT),
            "plugins.octoprint.org",
            "_plugins",
            "git_backup.md",
        )
        if os.path.exists(official_manifest):
            with open(official_manifest, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn('python: ">=3.7,<4"', content)


class TestSecurityAndOverrides(unittest.TestCase):
    def setUp(self):
        self.plugin = Git_backupPlugin()
        self.plugin._logger = MagicMock()
        self.plugin._settings = MagicMock()
        self.plugin._git_lock = MagicMock()
        self.plugin._plugin_manager = MagicMock()

    def test_template_autoescaped_enabled(self):
        # SEC-0007: Must override is_template_autoescaped to return True
        self.assertTrue(self.plugin.is_template_autoescaped())

    def test_template_configs_custom_bindings(self):
        configs = self.plugin.get_template_configs()
        self.assertIsInstance(configs, list)
        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0].get("type"), "settings")
        self.assertIs(configs[0].get("custom_bindings"), True)

    def test_api_security_attributes(self):
        self.assertTrue(self.plugin.is_api_protected())
        self.assertTrue(self.plugin.is_api_adminonly())

    def test_settings_restricted_paths(self):
        restricted = self.plugin.get_settings_restricted_paths()
        self.assertIn("admin", restricted)
        self.assertIn(["repo_url"], restricted["admin"])

    def test_no_sudo_or_apt_runtime_methods(self):
        # Ensure deprecated privilege-escalating methods are completely removed
        self.assertFalse(hasattr(self.plugin, "_sudo"))
        self.assertFalse(hasattr(self.plugin, "_api_apt_install"))
        self.assertFalse(hasattr(self.plugin, "_api_install_gh"))

    def test_api_commands_whitelist(self):
        commands = self.plugin.get_api_commands()
        self.assertEqual(
            set(commands.keys()),
            {"start_auth_login", "check_repo", "setup_git"},
        )
        self.assertNotIn("install_git", commands)
        self.assertNotIn("install_gh", commands)

    def test_source_code_clean_of_insecure_commands(self):
        # Ensure forbidden patterns do not exist in python or js sources
        forbidden = re.compile(
            r"\b(sudo|apt-get|install_git|install_gh|confirmDialog|installPackage)\b"
        )
        for root, _, files in os.walk(os.path.join(REPO_ROOT, "octoprint_git_backup")):
            for f in files:
                if f.endswith((".py", ".js", ".jinja2")):
                    filepath = os.path.join(root, f)
                    with open(filepath, "r", encoding="utf-8") as src:
                        content = src.read()
                    matches = forbidden.findall(content)
                    self.assertEqual(
                        matches,
                        [],
                        f"Forbidden keywords found in {filepath}: {matches}",
                    )


class TestThreadDaemonFlag(unittest.TestCase):
    def setUp(self):
        self.plugin = Git_backupPlugin()
        self.plugin.initialize()
        self.plugin._logger = MagicMock()
        self.plugin._settings = MagicMock()

    def test_ast_daemon_flag_is_true(self):
        init_file = os.path.join(REPO_ROOT, "octoprint_git_backup", "__init__.py")
        with open(init_file, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=init_file)

        daemon_kwargs = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check for threading.Thread(...)
                func = node.func
                is_thread = (
                    isinstance(func, ast.Attribute)
                    and func.attr == "Thread"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "threading"
                )
                if is_thread:
                    for kw in node.keywords:
                        if kw.arg == "daemon":
                            daemon_kwargs.append(
                                isinstance(kw.value, ast.Constant)
                                and kw.value.value is True
                            )

        self.assertGreater(len(daemon_kwargs), 0)
        self.assertTrue(
            all(daemon_kwargs),
            f"All threading.Thread instances must have daemon=True, found: {daemon_kwargs}",
        )

    @patch("threading.Thread")
    @patch("os.path.exists", return_value=True)
    def test_on_event_creates_daemon_thread(self, mock_exists, mock_thread_cls):
        mock_thread_instance = MagicMock()
        mock_thread_cls.return_value = mock_thread_instance

        self.plugin.on_event(
            "plugin_backup_backup_created",
            {"path": "/mock/backup.zip", "name": "backup.zip"},
        )

        mock_thread_cls.assert_called_once()
        _, kwargs = mock_thread_cls.call_args
        self.assertIs(kwargs.get("daemon"), True)
        self.assertEqual(kwargs.get("name"), "git_backup_push")
        self.assertEqual(kwargs.get("target"), self.plugin._push_backup_to_git)
        mock_thread_instance.start.assert_called_once()


class TestUrlExtraction(unittest.TestCase):
    def test_valid_github_urls(self):
        self.assertEqual(
            _extract_nwo("https://github.com/octoprint/OctoPrint.git"),
            "octoprint/OctoPrint",
        )
        self.assertEqual(
            _extract_nwo("https://github.com/octoprint/OctoPrint"),
            "octoprint/OctoPrint",
        )
        self.assertEqual(
            _extract_nwo("git@github.com:octoprint/OctoPrint.git"),
            "octoprint/OctoPrint",
        )
        self.assertEqual(
            _extract_nwo("git@github.com:MauroDruwel/OctoPrint-Git-Backup.git"),
            "MauroDruwel/OctoPrint-Git-Backup",
        )

    def test_invalid_urls(self):
        self.assertIsNone(_extract_nwo(""))
        self.assertIsNone(_extract_nwo("https://gitlab.com/octoprint/OctoPrint.git"))
        self.assertIsNone(_extract_nwo("not a url"))


class TestClientJavaScriptArchitecture(unittest.TestCase):
    def test_no_monkey_patching(self):
        js_file = os.path.join(
            REPO_ROOT, "octoprint_git_backup", "static", "js", "git_backup.js"
        )
        with open(js_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("OctoPrint.plugins.git_backup =", content)
        self.assertNotIn("OctoPrint.plugins =", content)
        self.assertNotIn("OctoPrint.plugins.git_backup.", content)

    def test_viewmodel_registration_and_elements(self):
        js_file = os.path.join(
            REPO_ROOT, "octoprint_git_backup", "static", "js", "git_backup.js"
        )
        with open(js_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("function Git_backupViewModel(parameters)", content)
        self.assertIn('elements: ["#settings_plugin_git_backup"]', content)
        self.assertIn("self.checkAuthStatus = function", content)
        self.assertIn("self.setupGit = function", content)
        self.assertIn("self.startAuthLogin = function", content)
        self.assertIn("self.checkRepo = function", content)

    def test_jinja2_template_custom_bindings(self):
        jinja_file = os.path.join(
            REPO_ROOT,
            "octoprint_git_backup",
            "templates",
            "git_backup_settings.jinja2",
        )
        with open(jinja_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn('<div id="settings_plugin_git_backup">', content)
        self.assertIn('data-bind="click: checkAuthStatus', content)
        self.assertIn('data-bind="html: authStatusHtml"', content)
        self.assertNotIn("OctoPrint.plugins.git_backup", content)


if __name__ == "__main__":
    unittest.main()
