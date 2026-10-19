/*
 * View model for OctoPrint-Git-Backup
 *
 * Author: Mauro Druwel
 * License: MIT
 */
$(function() {
    var _authPollInterval = null;
    var _repoCheckTimer = null;

    // ── Helper functions ──────────────────────────────────────────────────────

    function icon(type) {
        var colors = { check: "#468847", times: "#b94a48", minus: "#999", spin: "" };
        var cls = type === "spin" ? "fas fa-spinner fa-spin" : "fas fa-" + type;
        var style = colors[type] ? " style='color:" + colors[type] + "'" : "";
        return "<i class='" + cls + "'" + style + "></i>";
    }

    function actionLink(id, label) {
        return "<a href='#' id='git_backup_" + id + "' class='git-backup-action-link'>" + label + "</a>";
    }

    // ── Status HTML builder ───────────────────────────────────────────────────

    function buildStatusHtml(data) {
        var lines = [];  // each entry: {html, sub}

        function push(html)    { lines.push({html: html, sub: false}); }
        function pushSub(html) { lines.push({html: html, sub: true}); }

        // git
        if (data.git_installed) {
            push(icon("check") + " " + _.escape(data.git_version || "git installed"));
        } else {
            push(
                icon("times") + " <strong>git not found</strong> — install git via your OS package manager or from <a href='https://git-scm.com/downloads' target='_blank' rel='noopener noreferrer'>git-scm.com</a>"
            );
        }

        // gh auth
        if (data.gh_auth === true) {
            var line = icon("check") + " GitHub CLI authenticated";
            if (data.gh_username) line += " as <strong>@" + _.escape(data.gh_username) + "</strong>";
            push(line);

            // git credential helper sub-check (only relevant when gh is authed)
            if (data.git_credential_helper_set === true) {
                pushSub(icon("check") + " git configured to use gh credentials");
            } else if (data.git_credential_helper_set === false) {
                pushSub(
                    icon("times") + " git not configured to use gh credentials, " +
                    actionLink("setup_git_btn", "run gh auth setup-git")
                );
            }
        } else if (data.gh_auth === false) {
            push(
                icon("times") + " GitHub CLI not authenticated, " +
                actionLink("gh_login_btn", "run gh auth login")
            );
        } else {
            push(
                icon("minus") + " GitHub CLI not installed (optional) — see <a href='https://cli.github.com' target='_blank' rel='noopener noreferrer'>cli.github.com</a> for installation instructions"
            );
        }

        return lines.map(function(l) {
            var style = l.sub
                ? "margin-bottom:3px; margin-left:18px; font-size:0.95em; color:#555"
                : "margin-bottom:5px";
            return "<p style='" + style + "'>" + l.html + "</p>";
        }).join("");
    }

    // ── ViewModel ─────────────────────────────────────────────────────────────

    function Git_backupViewModel(parameters) {
        var self = this;
        self.settingsViewModel = parameters[0];
        self.settings = self.settingsViewModel.settings;

        var _authChecked = false;

        self.isCheckingAuth = ko.observable(false);
        self.authStatusHtml = ko.observable("<span class='muted'>Not checked yet.</span>");
        self.repoCheckHtml = ko.observable("");

        // ── Check auth status ─────────────────────────────────────────────────

        self.checkAuthStatus = function() {
            self.isCheckingAuth(true);
            self.authStatusHtml(icon("spin") + " Checking\u2026");

            OctoPrint.simpleApiGet("git_backup")
                .done(function(data) {
                    self.authStatusHtml(buildStatusHtml(data));
                })
                .fail(function() {
                    self.authStatusHtml("<span class='muted'>Could not check status.</span>");
                })
                .always(function() {
                    self.isCheckingAuth(false);
                });
        };

        // ── Repo privacy check ────────────────────────────────────────────────

        self.checkRepo = function(url) {
            if (!url || !url.trim()) {
                self.repoCheckHtml("");
                return;
            }

            self.repoCheckHtml("<i class='fas fa-spinner fa-spin'></i> Checking\u2026");

            OctoPrint.simpleApiCommand("git_backup", "check_repo", {url: url})
                .done(function(data) {
                    if (data.nwo === null) {
                        self.repoCheckHtml("<span class='muted'>Enter a valid GitHub URL to check visibility.</span>");
                    } else if (data.is_private === true) {
                        self.repoCheckHtml("<span style='color:#468847'>" + icon("check") + " <strong>" + _.escape(data.nwo) + "</strong> is private</span>");
                    } else if (data.is_private === false) {
                        self.repoCheckHtml(
                            "<span style='color:#b94a48'>" + icon("times") +
                            " <strong>" + _.escape(data.nwo) + "</strong> is <strong>public</strong>, backups may contain sensitive data!</span>"
                        );
                    } else {
                        self.repoCheckHtml("<span class='muted'>Could not verify visibility (repo not found or no access).</span>");
                    }
                })
                .fail(function() {
                    self.repoCheckHtml("");
                });
        };

        // ── Run gh auth setup-git ─────────────────────────────────────────────

        self.setupGit = function() {
            self.isCheckingAuth(true);
            self.authStatusHtml(icon("spin") + " Running gh auth setup-git\u2026");

            OctoPrint.simpleApiCommand("git_backup", "setup_git", {})
                .done(function(data) {
                    if (data.success) {
                        self.authStatusHtml(icon("check") + " Done! Refreshing\u2026");
                        setTimeout(function() { self.checkAuthStatus(); }, 800);
                    } else {
                        self.authStatusHtml(icon("times") + " Failed: " + _.escape(data.stderr || "unknown error"));
                        self.isCheckingAuth(false);
                    }
                })
                .fail(function() {
                    self.authStatusHtml(icon("times") + " Request failed.");
                    self.isCheckingAuth(false);
                });
        };

        // ── gh auth login (device flow) ───────────────────────────────────────

        self.startAuthLogin = function() {
            self.isCheckingAuth(true);
            self.authStatusHtml(icon("spin") + " Starting GitHub login\u2026");

            OctoPrint.simpleApiCommand("git_backup", "start_auth_login", {})
                .done(function(data) {
                    self.isCheckingAuth(false);
                    if (!data.success) {
                        var msg = data.error === "gh_not_found"
                            ? "GitHub CLI is not installed."
                            : "Could not start authentication. Is GitHub CLI installed?";
                        self.authStatusHtml(icon("times") + " " + msg);
                        return;
                    }

                    // Show device code prominently and start polling.
                    var html =
                        "<p style='margin-bottom:6px'><strong>Your one-time code:</strong></p>" +
                        "<p style='margin-bottom:10px'>" +
                            "<code style='font-size:1.5em;letter-spacing:3px;padding:5px 10px'>" + _.escape(data.code) + "</code>" +
                            " <button type='button' class='btn btn-mini' id='git_backup_copy_btn' data-code='" + _.escape(data.code) + "' style='margin-left:8px'>Copy</button>" +
                        "</p>" +
                        "<p style='margin-bottom:10px'>" +
                            "<a href='" + _.escape(data.url) + "' target='_blank' rel='noopener noreferrer' class='btn btn-primary btn-small'>" +
                            "<i class='fas fa-external-link-alt'></i> Open github.com/login/device</a>" +
                        "</p>" +
                        "<p class='muted' id='git_backup_auth_waiting'>" + icon("spin") + " Waiting for you to complete authentication\u2026</p>";
                    self.authStatusHtml(html);

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
                                self.checkAuthStatus();
                            }
                        });
                    }, 3000);
                })
                .fail(function() {
                    self.authStatusHtml(icon("times") + " Request failed.");
                    self.isCheckingAuth(false);
                });
        };

        // ── Event delegation for dynamically rendered action links ────────────

        $(document).on("click", "#settings_plugin_git_backup .git-backup-action-link", function(e) {
            e.preventDefault();
            var id = $(this).attr("id");
            if (id === "git_backup_setup_git_btn") {
                self.setupGit();
            } else if (id === "git_backup_gh_login_btn") {
                self.startAuthLogin();
            }
        });

        // ── Event delegation for copy button ──────────────────────────────────

        $(document).on("click", "#git_backup_copy_btn", function() {
            var $b = $(this);
            var code = $b.data("code");
            if (code) {
                if (navigator.clipboard) {
                    navigator.clipboard.writeText(code);
                } else {
                    var t = document.createElement("textarea");
                    t.value = code;
                    document.body.appendChild(t);
                    t.select();
                    document.execCommand("copy");
                    document.body.removeChild(t);
                }
                $b.text("Copied!");
                setTimeout(function() { $b.text("Copy"); }, 1500);
            }
        });

        // ── Settings lifecycle hook ───────────────────────────────────────────

        self.onSettingsShown = function() {
            if (!_authChecked) {
                _authChecked = true;
                self.checkAuthStatus();
            }

            // Debounced repo visibility check on URL field change.
            $("#git_backup_repo_url_input").off("input.gitbackup").on("input.gitbackup", function() {
                var url = $(this).val();
                clearTimeout(_repoCheckTimer);
                _repoCheckTimer = setTimeout(function() {
                    self.checkRepo(url);
                }, 700);
            });

            // Also check once on open with current saved value.
            setTimeout(function() {
                var currentUrl = $("#git_backup_repo_url_input").val();
                self.checkRepo(currentUrl);
            }, 300);
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: Git_backupViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#settings_plugin_git_backup"]
    });
});
