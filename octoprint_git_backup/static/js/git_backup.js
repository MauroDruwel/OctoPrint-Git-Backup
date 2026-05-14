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

        self.authStatus = ko.observable(null);
        self.authLoading = ko.observable(false);
        self._authChecked = false;
        var _requestId = 0;

        self.checkAuthStatus = function() {
            var current = ++_requestId;
            self.authLoading(true);
            OctoPrint.simpleApiGet("git_backup")
                .done(function(data) {
                    if (current === _requestId) self.authStatus(data);
                })
                .fail(function() {
                    if (current === _requestId) self.authStatus(null);
                })
                .always(function() {
                    if (current === _requestId) self.authLoading(false);
                });
        };

        self.onSettingsShown = function() {
            if (!self._authChecked) {
                self._authChecked = true;
                self.checkAuthStatus();
            }
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: Git_backupViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#settings_plugin_git_backup"]
    });
});
