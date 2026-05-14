/*
 * View model for OctoPrint-Git-Backup
 *
 * Author: Mauro Druwel
 * License: AGPL-3.0-or-later
 */
$(function() {
    function Git_backupViewModel(parameters) {
        var self = this;

        self.settingsViewModel = parameters[0];
        self.pluginSettings = self.settingsViewModel.settings.plugins.git_backup;
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: Git_backupViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#settings_plugin_git_backup"]
    });
});
