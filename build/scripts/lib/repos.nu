use common.nu [print-step print-bullets run-cmd dnf-clean]

export def render-fedora-url [template: string, fedora: string] {
  $template | str replace "{fedora}" $fedora
}

export def append-priority [dry_run: bool, file: string, value: int] {
  let repo_path = $"/etc/yum.repos.d/($file)"

  if $dry_run {
    print $"DRY-RUN: append priority=($value) -> ($repo_path)"
    return
  }

  if not ($repo_path | path exists) {
    print $"missing repo file: ($repo_path)"
    exit 1
  }

  $"\npriority=($value)\n" | save --append --raw $repo_path
}

export def install-rpmfusion [dry_run: bool, repos_cfg] {
  # The Containerfile bootstrap already installs rpmfusion. Re-running
  # `dnf install <url>` here would just re-download it, so skip when present.
  if not $dry_run {
    let installed = (^rpm -q rpmfusion-free-release | complete | get exit_code) == 0
    if $installed {
      print-step "rpmfusion already installed (bootstrap), skipping"
      return
    }
  }

  let fedora = if $dry_run {
    "<fedora>"
  } else {
    ^rpm -E "%fedora" | str trim
  }
  let urls = ($repos_cfg.rpmfusion_release_templates | each {|template| render-fedora-url $template $fedora })

  print-step "enabling rpmfusion"
  print-bullets $urls
  run-cmd $dry_run "dnf" (["install" "-y"] | append $urls)
}

export def enable-config-manager-options [dry_run: bool, options] {
  print-step "configuring dnf config-manager options"
  print-bullets $options

  for option in $options {
    run-cmd $dry_run "dnf" ["config-manager" "setopt" $option]
  }
}

export def disable-matching-repos [dry_run: bool, pattern: string] {
  let repo_files = (glob $"/etc/yum.repos.d/($pattern)")

  print-step $"disabling repos matching ($pattern)"

  if (($repo_files | length) == 0) {
    print "  - no matching repos found"
    return
  }

  print-bullets $repo_files

  for repo_file in $repo_files {
    run-cmd $dry_run "sed" ["-i" "s/^enabled=1/enabled=0/g" $repo_file]
  }
}

export def add-external-repos [dry_run: bool, repos] {
  if (($repos | length) == 0) {
    return
  }

  print-step "adding external repos via dnf config-manager"
  print-bullets $repos

  for repo in $repos {
    run-cmd $dry_run "dnf" ["config-manager" "addrepo" "--from-repofile" $repo]
  }
}

export def enable-copr-groups [dry_run: bool, copr_cfg] {
  for group in $copr_cfg.enable_order {
    let repos = ($copr_cfg.groups | get $group)
    print-step $"enabling copr group: ($group)"
    print-bullets $repos

    for repo in $repos {
      run-cmd $dry_run "dnf" ["copr" "enable" "-y" $repo]
    }
  }
}

export def apply-priority-overrides [dry_run: bool, overrides] {
  print-step "applying repo priority overrides"

  for override in $overrides {
    print $"  - ($override.file) => priority=($override.value)"
    append-priority $dry_run $override.file $override.value
  }
}

export def run-repo-stage [dry_run: bool, repos_cfg] {
  install-rpmfusion $dry_run $repos_cfg
  # external repos must exist before config-manager setopt runs, since setopt
  # targets repo ids defined inside those repo files.
  add-external-repos $dry_run $repos_cfg.external_repos
  enable-config-manager-options $dry_run $repos_cfg.config_manager_setopts
  disable-matching-repos $dry_run $repos_cfg.disable_glob
  enable-copr-groups $dry_run $repos_cfg.copr
  apply-priority-overrides $dry_run $repos_cfg.priority_overrides
  dnf-clean $dry_run
}
