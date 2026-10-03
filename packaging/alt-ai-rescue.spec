Name: alt-ai-rescue
Version: 1.0
Release: alt6

Summary: ALT AI Rescue with a local model
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

Requires: alt-ai-rescue-local = %version-%release

%description
Installs the ALT AI Rescue recovery environment and local model support.

%package core
Summary: Recovery boot mode for ALT Linux with an API model
Group: System/Configuration/Boot and Init
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

%description core
Provides the ALT AI Rescue recovery environment and support for
OpenAI-compatible chat/completions APIs. Configure the model in
/etc/alt-ai-rescue/model.conf.

%package local
Summary: Local llama.cpp model support for ALT AI Rescue
Group: System/Configuration/Boot and Init
Requires: alt-ai-rescue-core = %version-%release
Requires: /usr/bin/llama-server
Requires: /usr/bin/curl
Requires: diffutils
Requires: sed

%description local
Adds the llama.cpp server and local model installer to ALT AI Rescue.

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

find src/ai_agent -type f -name '*.py' | while IFS= read -r module; do
    relative_path="${module#src/}"
    install -Dm644 \
        "$module" \
        "%buildroot%_libexecdir/alt-ai-rescue/$relative_path"
done

install -d -m700 %buildroot%_sysconfdir/alt-ai-rescue
install -m600 \
    src/ai_agent/selector_model/model.conf \
    %buildroot%_sysconfdir/alt-ai-rescue/model.conf

# Keep the factory settings to detect whether the user changed model.conf.
install -Dm644 \
    src/ai_agent/selector_model/model.conf \
    %buildroot%_datadir/alt-ai-rescue/model.conf.default

install -Dm644 \
    systemd/alt-ai-rescue.service \
    %buildroot%_unitdir/alt-ai-rescue.service

install -Dm644 \
    systemd/alt-ai-rescue.target \
    %buildroot%_unitdir/alt-ai-rescue.target

install -Dm644 \
    systemd/alt-ai-rescue-model-sync.service \
    %buildroot%_unitdir/alt-ai-rescue-model-sync.service

install -Dm644 \
    systemd/alt-ai-rescue-model-sync.path \
    %buildroot%_unitdir/alt-ai-rescue-model-sync.path

install -Dm755 \
    grub/42_alt_ai_rescue \
    %buildroot%_sysconfdir/grub.d/42_alt_ai_rescue

install -Dm755 \
    src/model_controller/install-model \
    %buildroot%_libexecdir/alt-ai-rescue/install-model

install -Dm644 \
    src/model_controller/model_install.conf \
    %buildroot%_datadir/alt-ai-rescue/model_install.conf

install -Dm644 \
    systemd/alt-ai-rescue-llama.service \
    %buildroot%_unitdir/alt-ai-rescue-llama.service

%post local
%systemd_post alt-ai-rescue-llama.service
# Older releases enabled llama.cpp directly from the rescue target.
systemctl disable alt-ai-rescue-llama.service >/dev/null 2>&1 || :
if ! %_libexecdir/alt-ai-rescue/install-model; then
    exit 1
fi
model_config=%_sysconfdir/alt-ai-rescue/model.conf
default_config=%_datadir/alt-ai-rescue/model.conf.default
# Keep an existing API choice when the local package is added.
if [ "$1" -eq 1 ] && cmp -s "$model_config" "$default_config"; then
    sed -i 's/^local = false$/local = true/' "$model_config" || exit 1
fi
%systemd_post_with_restart alt-ai-rescue-llama.service

%preun local
model_config=%_sysconfdir/alt-ai-rescue/model.conf
if [ "$1" -eq 0 ]; then
    if [ -f "$model_config" ]; then
        sed -i 's/^[[:space:]]*local[[:space:]]*=.*/local = false/' "$model_config" || exit 1
    fi
fi
%systemd_preun alt-ai-rescue-llama.service
if [ "$1" -eq 0 ]; then
    echo "Removing ALT AI Rescue model data from %_localstatedir/alt-ai-rescue..."
    rm -rf -- "%_localstatedir/alt-ai-rescue" || exit 1
fi

%postun local
%systemd_postun alt-ai-rescue-llama.service

%post core
%systemd_post alt-ai-rescue.service alt-ai-rescue-model-sync.service alt-ai-rescue-model-sync.path alt-ai-rescue.target

%preun core
%systemd_preun alt-ai-rescue.service alt-ai-rescue-model-sync.service alt-ai-rescue-model-sync.path alt-ai-rescue.target

%postun core
%systemd_postun alt-ai-rescue.service alt-ai-rescue-model-sync.service alt-ai-rescue-model-sync.path alt-ai-rescue.target

%files
# The main package contains only dependencies.

%files local
%_libexecdir/alt-ai-rescue/install-model

%_datadir/alt-ai-rescue/model_install.conf

%_unitdir/alt-ai-rescue-llama.service

%files core
%dir %_libexecdir/alt-ai-rescue
%_libexecdir/alt-ai-rescue/alt-ai-rescue-menu
%_libexecdir/alt-ai-rescue/alt-ai-rescue-collect
%_libexecdir/alt-ai-rescue/alt-ai-rescue-ai
%_libexecdir/alt-ai-rescue/collector
%_libexecdir/alt-ai-rescue/ai_agent

%dir %_datadir/alt-ai-rescue
%_datadir/alt-ai-rescue/model.conf.default

%attr(0700,root,root) %dir %_sysconfdir/alt-ai-rescue
%config(noreplace) %attr(0600,root,root) %_sysconfdir/alt-ai-rescue/model.conf

%_unitdir/alt-ai-rescue.service
%_unitdir/alt-ai-rescue-model-sync.service
%_unitdir/alt-ai-rescue-model-sync.path
%_unitdir/alt-ai-rescue.target

%_sysconfdir/grub.d/42_alt_ai_rescue
