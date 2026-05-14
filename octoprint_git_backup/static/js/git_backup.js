/*
 * View model for OctoPrint-Git-Backup
 *
 * Author: Mauro Druwel
 * License: AGPL-3.0-or-later
 */
$(function() {
    // Expose checkAuthStatus globally so the template's inline click handler can reach it
    // regardless of which KO binding context wraps the settings panel.
    OctoPrint.plugins = OctoPrint.plugins || {};
    OctoPrint.plugins.git_backup = OctoPrint.plugins.git_backup || {};

    function buildStatusHtml(data) {
        var lines = [];

        if (data.git_installed) {
            lines.push('<i class="fas fa-check" style="color:#468847"></i> ' + _.escape(data.git_version || "git installed"));
        } else {
            lines.push('<i class="fas fa-times" style="color:#b94a48"></i> <strong>git not found</strong> — install git on your OctoPrint host');
        }

        if (data.gh_auth === true) {
            var line = '<i class="fas fa-check" style="color:#468847"></i> GitHub CLI authenticated';
            if (data.gh_username) line += ' as <strong>@' + _.escape(data.gh_username) + '</strong>';
            lines.push(line);
        } else if (data.gh_auth === false) {
            lines.push('<i class="fas fa-times" style="color:#b94a48"></i> GitHub CLI not authenticated — run <code>gh auth login</code>');
        } else {
            lines.push('<i class="fas fa-minus" style="color:#999"></i> GitHub CLI not installed — <a href="https://cli.github.com" target="_blank" rel="noopener noreferrer">install gh</a> for HTTPS auth, or use an SSH URL');
        }

        return lines.map(function(l) {
            return '<p style="margin-bottom:4px">' + l + '</p>';
        }).join('');
    }

    function Git_backupViewModel(parameters) {
        var self = this;
        self.settingsViewModel = parameters[0];

        var _authChecked = false;
        var _requestId = 0;

        OctoPrint.plugins.git_backup.checkAuthStatus = function() {
            var current = ++_requestId;
            var $container = $("#git_backup_auth_status");
            var $btn = $("#git_backup_auth_refresh");

            $container.html('<i class="fas fa-spinner fa-spin"></i> Checking\u2026');
            $btn.prop("disabled", true);

            OctoPrint.simpleApiGet("git_backup")
                .done(function(data) {
                    if (current !== _requestId) return;
                    $container.html(buildStatusHtml(data));
                })
                .fail(function() {
                    if (current !== _requestId) return;
                    $container.html('<span class="muted">Could not check authentication status.</span>');
                })
                .always(function() {
                    if (current !== _requestId) return;
                    $btn.prop("disabled", false);
                });
        };

        self.onSettingsShown = function() {
            if (!_authChecked) {
                _authChecked = true;
                OctoPrint.plugins.git_backup.checkAuthStatus();
            }
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: Git_backupViewModel,
        dependencies: ["settingsViewModel"]
        // No elements — lifecycle callbacks (onSettingsShown) still fire on all ViewModels.
        // Settings fields are bound automatically by OctoPrint via custom_bindings=False.
    });
});
