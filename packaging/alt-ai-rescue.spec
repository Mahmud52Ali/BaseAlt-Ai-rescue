Name: alt-ai-rescue
Version: 1.0
Release: alt1

Summary: Recovery boot mode for ALT Linux
License: GPL-3.0-or-later
Group: System/Configuration/Boot and Init

Source: %name-%version.tar.xz

BuildArch: noarch
AutoReqProv: nopython

BuildRequires(pre): rpm-macros-systemd
BuildRequires(pre): rpm-build-python
BuildRequires(pre): rpm-build-python3
BuildRequires: /usr/bin/python3

%add_python3_req_skip ai_agent.tools.util.validator
%add_python3_req_skip collector
%add_python3_req_skip journal_scanner
%add_python3_req_skip boot_selector

Requires: grub-common
Requires: /bin/bash
Requires: /sbin/agetty
Requires: /usr/bin/clear
Requires: util-linux
Requires: lsblk
Requires: coreutils
Requires: /usr/bin/systemctl
Requires: /usr/bin/python3
Requires: /usr/bin/journalctl
Requires: rpm
Requires: smartmontools
Requires: make-initrd
Requires: /usr/bin/llama-server
Requires: /usr/bin/curl

%description
ALT AI Rescue adds a dedicated recovery boot mode to GRUB.

%prep
%setup

%build

%install
install -Dm755 \
    src/alt-ai-rescue-menu \
    %buildroot%_libexecdir/alt-ai-rescue/alt-ai-rescue-menu

install -Dm755 \
    src/alt-ai-rescue-collect \
    %buildroot%_libexecdir/alt-ai-rescue/alt-ai-rescue-collect

find src/collector -type f -name '*.py' | while IFS= read -r module; do
    relative_path="${module#src/}"
    install -Dm644 \
        "$module" \
        "%buildroot%_libexecdir/alt-ai-rescue/$relative_path"
done

install -Dm755 \
    src/alt-ai-rescue-ai \
    %buildroot%_libexecdir/alt-ai-rescue/alt-ai-rescue-ai

install -Dm755 \
    src/alt-ai-rescue-download-model \
    %buildroot%_libexecdir/alt-ai-rescue/alt-ai-rescue-download-model

find src/ai_agent -type f -name '*.py' | while IFS= read -r module; do
    relative_path="${module#src/}"
    install -Dm644 \
        "$module" \
        "%buildroot%_libexecdir/alt-ai-rescue/$relative_path"
done

install -Dm644 \
    systemd/alt-ai-rescue.service \
    %buildroot%_unitdir/alt-ai-rescue.service

install -Dm644 \
    systemd/alt-ai-rescue.target \
    %buildroot%_unitdir/alt-ai-rescue.target

install -Dm644 \
    systemd/alt-ai-rescue-llama.service \
    %buildroot%_unitdir/alt-ai-rescue-llama.service

install -d \
    %buildroot%_datadir/alt-ai-rescue/models

install -Dm755 \
    grub/42_alt_ai_rescue \
    %buildroot%_sysconfdir/grub.d/42_alt_ai_rescue

%post
%systemd_post alt-ai-rescue.service alt-ai-rescue-llama.service alt-ai-rescue.target
%_libexecdir/alt-ai-rescue/alt-ai-rescue-download-model || :

%preun
%systemd_preun alt-ai-rescue.service alt-ai-rescue-llama.service alt-ai-rescue.target

%postun
%systemd_postun alt-ai-rescue.service alt-ai-rescue-llama.service alt-ai-rescue.target

%files
%dir %_libexecdir/alt-ai-rescue
%_libexecdir/alt-ai-rescue/alt-ai-rescue-menu
%_libexecdir/alt-ai-rescue/alt-ai-rescue-collect
%_libexecdir/alt-ai-rescue/alt-ai-rescue-ai
%_libexecdir/alt-ai-rescue/alt-ai-rescue-download-model
%_libexecdir/alt-ai-rescue/collector

%_libexecdir/alt-ai-rescue/ai_agent

%dir %_datadir/alt-ai-rescue
%dir %_datadir/alt-ai-rescue/models

%_unitdir/alt-ai-rescue.service
%_unitdir/alt-ai-rescue-llama.service
%_unitdir/alt-ai-rescue.target

%_sysconfdir/grub.d/42_alt_ai_rescue

