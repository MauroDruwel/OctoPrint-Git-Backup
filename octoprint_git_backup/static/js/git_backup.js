/*
 * View model for OctoPrint-Git-Backup
 *
 * Author: Mauro Druwel
 * License: MIT
 */
$(function() {
    OctoPrint.plugins = OctoPrint.plugins || {};
    OctoPrint.plugins.git_backup = OctoPrint.plugins.git_backup || {};

    var _authPollInterval = null;

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
                icon("times") + " <strong>git not found</strong> — " +
                actionLink("install_git_btn", "install git", "OctoPrint.plugins.git_backup.installPackage('git')")
            );
        }

        // gh auth
        if (data.gh_auth === true) {
            var line = icon("check") + " GitHub CLI authenticated";
            if (data.gh_username) line += " as <strong>@" + _.escape(data.gh_username) + "</strong>";
            push(line);

            // git credential helper sub-check (only relevant when gh is authed)
            if (data.git_credential_helper_set === true) {
                push(icon("check") + " git configured to use gh credentials");
            } else if (data.git_credential_helper_set === false) {
                push(
                    icon("times") + " git not configured to use gh credentials — " +
                    actionLink("setup_git_btn", "run gh auth setup-git", "OctoPrint.plugins.git_backup.setupGit()")
                );
            }
        } else if (data.gh_auth === false) {
            push(
                icon("times") + " GitHub CLI not authenticated — " +
                actionLink("gh_login_btn", "run gh auth login", "OctoPrint.plugins.git_backup.startAuthLogin()")
            );
        } else {
            push(
                icon("minus") + " GitHub CLI not installed — " +
                actionLink("install_gh_btn", "install gh CLI", "OctoPrint.plugins.git_backup.installPackage('gh')") +
                " or see <a href='https://cli.github.com' target='_blank' rel='noopener noreferrer'>manual instructions</a>"
            );
        }

        return lines.map(function(l) {
            var style = l.sub
                ? "margin-bottom:3px; margin-left:18px; font-size:0.95em; color:#555"
                : "margin-bottom:5px";
            return "<p style='" + style + "'>" + l.html + "</p>";
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
                    $span.html("<span style='color:#468847'>" + icon("check") + " <strong>" + _.escape(data.nwo) + "</strong> is private</span>");
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

    OctoPrint.plugins.git_backup.setupGit = function() {
        var $container = $("#git_backup_auth_status");
        var $btn = $("#git_backup_auth_refresh");
        $container.html(icon("spin") + " Running gh auth setup-git\u2026");
        $btn.prop("disabled", true);
        OctoPrint.simpleApiCommand("git_backup", "setup_git", {})
            .done(function(data) {
                if (data.success) {
                    $container.html(icon("check") + " Done! Refreshing\u2026");
                    setTimeout(OctoPrint.plugins.git_backup.checkAuthStatus, 800);
                } else {
                    $container.html(icon("times") + " Failed: " + _.escape(data.stderr || "unknown error"));
                    $btn.prop("disabled", false);
                }
            })
            .fail(function() {
                $container.html(icon("times") + " Request failed.");
                $btn.prop("disabled", false);
            });
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

    // ── Simple confirm dialog (Bootstrap modal, no bootbox needed) ────────────

    function confirmDialog(title, bodyHtml, confirmLabel, onConfirm) {
        var id = "git_backup_confirm_modal";
        $("#" + id).remove();
        var html =
            "<div id='" + id + "' class='modal hide fade' tabindex='-1'>" +
              "<div class='modal-header'><h3>" + title + "</h3></div>" +
              "<div class='modal-body'>" + bodyHtml + "</div>" +
              "<div class='modal-footer'>" +
                "<button class='btn' data-dismiss='modal'>Cancel</button>" +
                "<button class='btn btn-primary' id='" + id + "_ok'>" + confirmLabel + "</button>" +
              "</div>" +
            "</div>";
        $("body").append(html);
        var $modal = $("#" + id);
        $modal.on("hidden", function() { $modal.remove(); });
        $("#" + id + "_ok").on("click", function() {
            $modal.modal("hide");
            onConfirm();
        });
        $modal.modal("show");
    }

    // ── Install git / gh CLI ──────────────────────────────────────────────────

    OctoPrint.plugins.git_backup.installPackage = function(pkg) {
        var isGit  = pkg === "git";
        var label  = isGit ? "git" : "GitHub CLI (gh)";
        var cmdLine = isGit
            ? "<code>apt-get install -y git</code>"
            : "<code>apt-get install -y gh</code> (falls back to full GitHub CLI repo setup if gh isn't in your default apt sources)";

        confirmDialog(
            "Install " + label + "?",
            "<p>This will run the following on your OctoPrint host:</p>" +
            "<p>" + cmdLine + "</p>" +
            "<p class='muted' style='margin-bottom:0'>Requires apt (Debian / Ubuntu / Raspberry Pi OS). On other systems, install " + label + " manually.</p>",
            "Install",
            function() {
                var $container = $("#git_backup_auth_status");
                var $btn = $("#git_backup_auth_refresh");

                $container.html(icon("spin") + " Installing " + label + "\u2026 (this may take a minute)");
                $btn.prop("disabled", true);

                OctoPrint.simpleApiCommand("git_backup", isGit ? "install_git" : "install_gh", {})
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
            }
        );
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

            // Also check once on open with the current saved value — defer so
            // KnockoutJS has time to populate the input before we read it.
            setTimeout(function() {
                var currentUrl = $("#git_backup_repo_url_input").val();
                OctoPrint.plugins.git_backup.checkRepo(currentUrl);
            }, 300);
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: Git_backupViewModel,
        dependencies: ["settingsViewModel"]
    });
});
