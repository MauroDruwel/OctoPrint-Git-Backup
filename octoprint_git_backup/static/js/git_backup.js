/*
 * View model for OctoPrint-Git-Backup
 *
 * Author: Mauro Druwel
 * License: AGPL-3.0-or-later
 */
$(function() {
    OctoPrint.plugins = OctoPrint.plugins || {};
    OctoPrint.plugins.git_backup = OctoPrint.plugins.git_backup || {};

    var _authPollInterval = null;

    // ── Status HTML builder ───────────────────────────────────────────────────

    function buildStatusHtml(data) {
        var lines = [];

        // git
        if (data.git_installed) {
            lines.push(icon("check") + " " + _.escape(data.git_version || "git installed"));
        } else {
            lines.push(
                icon("times") + " <strong>git not found</strong> — " +
                actionLink("install_git_btn", "install git", "OctoPrint.plugins.git_backup.installPackage('git')")
            );
        }

        // gh auth
        if (data.gh_auth === true) {
            var line = icon("check") + " GitHub CLI authenticated";
            if (data.gh_username) line += " as <strong>@" + _.escape(data.gh_username) + "</strong>";
            lines.push(line);
        } else if (data.gh_auth === false) {
            lines.push(
                icon("times") + " GitHub CLI not authenticated — " +
                actionLink("gh_login_btn", "run gh auth login", "OctoPrint.plugins.git_backup.startAuthLogin()")
            );
        } else {
            // gh not installed
            lines.push(
                icon("minus") + " GitHub CLI not installed — " +
                actionLink("install_gh_btn", "install gh CLI", "OctoPrint.plugins.git_backup.installPackage('gh')") +
                " or see <a href='https://cli.github.com' target='_blank' rel='noopener noreferrer'>manual instructions</a>"
            );
        }

        return lines.map(function(l) {
            return "<p style='margin-bottom:5px'>" + l + "</p>";
        }).join("");
    }

    function icon(type) {
        var colors = { check: "#468847", times: "#b94a48", minus: "#999", spin: "" };
        var cls = type === "spin" ? "fas fa-spinner fa-spin" : "fas fa-" + type;
        var style = colors[type] ? " style='color:" + colors[type] + "'" : "";
        return "<i class='" + cls + "'" + style + "></i>";
    }

    function actionLink(id, label, onclick) {
        return "<a href='#' id='git_backup_" + id + "' onclick=\"" + onclick + "; return false;\">" + label + "</a>";
    }

    // ── Repo privacy check ────────────────────────────────────────────────────

    var _repoCheckTimer = null;

    OctoPrint.plugins.git_backup.checkRepo = function(url) {
        var $span = $("#git_backup_repo_check");
        if (!url || !url.trim()) { $span.html(""); return; }

        $span.html("<i class='fas fa-spinner fa-spin'></i> Checking\u2026");

        OctoPrint.simpleApiCommand("git_backup", "check_repo", {url: url})
            .done(function(data) {
                if (data.nwo === null) {
                    $span.html("<span class='muted'>Enter a valid GitHub URL to check visibility.</span>");
                } else if (data.is_private === true) {
                    $span.html(icon("check") + " <strong>" + _.escape(data.nwo) + "</strong> is private");
                } else if (data.is_private === false) {
                    $span.html(
                        "<span style='color:#b94a48'>" + icon("times") +
                        " <strong>" + _.escape(data.nwo) + "</strong> is <strong>public</strong> — backups may contain sensitive data!</span>"
                    );
                } else {
                    $span.html("<span class='muted'>Could not verify visibility (repo not found or no access).</span>");
                }
            })
            .fail(function() { $span.html(""); });
    };

    // ── Check auth status ─────────────────────────────────────────────────────

    OctoPrint.plugins.git_backup.checkAuthStatus = function() {
        var $container = $("#git_backup_auth_status");
        var $btn = $("#git_backup_auth_refresh");

        $container.html(icon("spin") + " Checking\u2026");
        $btn.prop("disabled", true);

        OctoPrint.simpleApiGet("git_backup")
            .done(function(data) { $container.html(buildStatusHtml(data)); })
            .fail(function() { $container.html("<span class='muted'>Could not check status.</span>"); })
            .always(function() { $btn.prop("disabled", false); });
    };

    // ── Install git / gh CLI ──────────────────────────────────────────────────

    OctoPrint.plugins.git_backup.installPackage = function(pkg) {
        var label = pkg === "git" ? "git" : "GitHub CLI";
        var $container = $("#git_backup_auth_status");
        var $btn = $("#git_backup_auth_refresh");

        $container.html(icon("spin") + " Installing " + label + "\u2026 (this may take a minute)");
        $btn.prop("disabled", true);

        OctoPrint.simpleApiCommand("git_backup", pkg === "git" ? "install_git" : "install_gh", {})
            .done(function(data) {
                if (data.success) {
                    $container.html(icon("check") + " " + label + " installed! Refreshing\u2026");
                    setTimeout(OctoPrint.plugins.git_backup.checkAuthStatus, 1200);
                } else {
                    $container.html(
                        icon("times") + " Installation failed. Try manually:<br>" +
                        "<code>apt-get install -y " + _.escape(pkg) + "</code>" +
                        (data.stderr ? "<br><small class='muted'>" + _.escape(data.stderr) + "</small>" : "")
                    );
                    $btn.prop("disabled", false);
                }
            })
            .fail(function() {
                $container.html(icon("times") + " Request failed.");
                $btn.prop("disabled", false);
            });
    };

    // ── gh auth login (device flow) ───────────────────────────────────────────

    OctoPrint.plugins.git_backup.startAuthLogin = function() {
        var $container = $("#git_backup_auth_status");
        var $btn = $("#git_backup_auth_refresh");

        $container.html(icon("spin") + " Starting GitHub login\u2026");
        $btn.prop("disabled", true);

        OctoPrint.simpleApiCommand("git_backup", "start_auth_login", {})
            .done(function(data) {
                $btn.prop("disabled", false);
                if (!data.success) {
                    var msg = data.error === "gh_not_found"
                        ? "GitHub CLI is not installed."
                        : "Could not start authentication. Is GitHub CLI installed?";
                    $container.html(icon("times") + " " + msg);
                    return;
                }

                // Show device code prominently and start polling.
                $container.html(
                    "<p style='margin-bottom:6px'><strong>Your one-time code:</strong></p>" +
                    "<p style='margin-bottom:10px'>" +
                        "<code style='font-size:1.5em;letter-spacing:3px;padding:5px 10px'>" + _.escape(data.code) + "</code>" +
                        " <button type='button' class='btn btn-mini' id='git_backup_copy_btn' style='margin-left:8px'>Copy</button>" +
                    "</p>" +
                    "<p style='margin-bottom:10px'>" +
                        "<a href='" + _.escape(data.url) + "' target='_blank' rel='noopener noreferrer' class='btn btn-primary btn-small'>" +
                        "<i class='fas fa-external-link-alt'></i> Open github.com/login/device</a>" +
                    "</p>" +
                    "<p class='muted' id='git_backup_auth_waiting'>" + icon("spin") + " Waiting for you to complete authentication\u2026</p>"
                );

                // Copy button
                $("#git_backup_copy_btn").on("click", function() {
                    var $b = $(this);
                    if (navigator.clipboard) {
                        navigator.clipboard.writeText(data.code);
                    } else {
                        var t = document.createElement("textarea");
                        t.value = data.code;
                        document.body.appendChild(t);
                        t.select();
                        document.execCommand("copy");
                        document.body.removeChild(t);
                    }
                    $b.text("Copied!");
                    setTimeout(function() { $b.text("Copy"); }, 1500);
                });

                // Poll gh auth status every 3 s until authenticated or 5 min elapsed.
                if (_authPollInterval) clearInterval(_authPollInterval);
                var pollDeadline = Date.now() + 5 * 60 * 1000;
                _authPollInterval = setInterval(function() {
                    if (Date.now() > pollDeadline) {
                        clearInterval(_authPollInterval);
                        $("#git_backup_auth_waiting").text("Code expired. Click Refresh to try again.");
                        return;
                    }
                    OctoPrint.simpleApiGet("git_backup").done(function(s) {
                        if (s.gh_auth === true) {
                            clearInterval(_authPollInterval);
                            OctoPrint.plugins.git_backup.checkAuthStatus();
                        }
                    });
                }, 3000);
            })
            .fail(function() {
                $container.html(icon("times") + " Request failed.");
                $btn.prop("disabled", false);
            });
    };

    // ── ViewModel ─────────────────────────────────────────────────────────────

    function Git_backupViewModel(parameters) {
        var self = this;
        self.settingsViewModel = parameters[0];

        var _authChecked = false;

        self.onSettingsShown = function() {
            if (!_authChecked) {
                _authChecked = true;
                OctoPrint.plugins.git_backup.checkAuthStatus();
            }

            // Debounced repo visibility check on URL field change.
            $("#git_backup_repo_url_input").off("input.gitbackup").on("input.gitbackup", function() {
                var url = $(this).val();
                clearTimeout(_repoCheckTimer);
                _repoCheckTimer = setTimeout(function() {
                    OctoPrint.plugins.git_backup.checkRepo(url);
                }, 700);
            });

            // Also check once on open with the current saved value.
            var currentUrl = $("#git_backup_repo_url_input").val();
            OctoPrint.plugins.git_backup.checkRepo(currentUrl);
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: Git_backupViewModel,
        dependencies: ["settingsViewModel"]
    });
});
