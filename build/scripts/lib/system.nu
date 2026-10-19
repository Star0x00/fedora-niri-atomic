use common.nu [print-step print-bullets run-cmd]

export def configure-flatpak [dry_run: bool, flatpak_cfg] {
  print-step "configuring flatpak remotes"

  for remote in $flatpak_cfg.remotes {
    print $"  - ($remote.name) => ($remote.url)"
    run-cmd $dry_run "flatpak" ["remote-add" "--if-not-exists" $remote.name $remote.url]
  }
}

export def refresh-font-cache [dry_run: bool] {
  print-step "refreshing font cache"
  run-cmd $dry_run "fc-cache" ["-fv"]
}

export def enable-services [dry_run: bool, services] {
  print-step "enabling system services"
  run-cmd $dry_run "systemd-sysusers" []
  run-cmd $dry_run "grpck" ["-s"]
  run-cmd $dry_run "pwck" ["-s"]
  print-bullets $services

  for service in $services {
    run-cmd $dry_run "systemctl" ["enable" $service]
  }
}

export def disable-services [dry_run: bool, services] {
  print-step "masking unwanted system services"
  print-bullets $services

  for service in $services {
    run-cmd $dry_run "systemctl" ["mask" $service]
  }
}

export def run-bootc-lint [dry_run: bool] {
  print-step "running bootc container lint"
  run-cmd $dry_run "bootc" ["container" "lint"]
}

export def run-system-stage [dry_run: bool, system_cfg] {
  configure-flatpak $dry_run $system_cfg.flatpak
  refresh-font-cache $dry_run
  enable-services $dry_run $system_cfg.services.enable
  disable-services $dry_run $system_cfg.services.disable
  run-bootc-lint $dry_run
}
