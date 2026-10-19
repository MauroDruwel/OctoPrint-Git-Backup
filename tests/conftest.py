import os
import sys
import types
from unittest.mock import MagicMock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Setup mock modules for Flask if not installed
if "flask" not in sys.modules:
    flask_mock = MagicMock()
    flask_mock.jsonify = lambda x: x
    sys.modules["flask"] = flask_mock

# Setup mock package for OctoPrint if not installed
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
