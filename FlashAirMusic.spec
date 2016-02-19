BuildArch:          noarch
BuildRequires:      python3-devel
BuildRequires:      systemd
Group:              Development/Libraries
License:            MIT
Name:               %{getenv:NAME}
Release:            1%{?dist}
Requires(post):     systemd
Requires(postun):   systemd
Requires(pre):      shadow-utils
Requires(preun):    systemd
Requires:           ffmpeg
Requires:           python3-docopt
Requires:           python3-requests
Source0:            %{name}-%{version}.tar.gz
Source1:            https://pypi.python.org/packages/source/d/docoptcfg/docoptcfg-1.0.1.tar.gz
Source2:            https://pypi.python.org/packages/source/m/mutagen/mutagen-1.31.tar.gz
Summary:            %{getenv:SUMMARY}
URL:                %{getenv:URL}
Version:            %{getenv:VERSION}

%global base_module %{lua: print(rpm.expand('%{name}'):gsub('([^\n])(%u)', '%1_%2'):lower()) }
%global daemon_group %{name}
%global daemon_user %{name}

%description
%{lua:
    name = rpm.expand('%{name}')
    data = io.open('README.rst'):read('*a')
    description = data:match('^=+\n' .. name .. '\n=+\n\n(.-)\n\n.. image::')
    print(description)
}

%prep
%autosetup -n %{name}-%{version}

%build
%{__tar} -C %{base_module}/_3rdparty --strip 1 -xzf %{SOURCE1} docoptcfg-*/docoptcfg.py
%{__tar} -C %{base_module}/_3rdparty --strip 1 -xzf %{SOURCE2} mutagen-*/mutagen
%py3_build

%install
%py3_install
%{__install} -d -m 0755 %{buildroot}%{_localstatedir}/log/%{name}
%{__install} -d -m 0755 %{buildroot}%{_localstatedir}/spool/%{name}
%{__install} -d -m 0755 %{buildroot}%{_sysconfdir}/%{name}
%{__install} -d -m 0755 %{buildroot}%{_sysconfdir}/logrotate.d
%{__install} -d -m 0755 %{buildroot}%{_unitdir}
%{__install} -m 0644 %{name}.ini %{buildroot}%{_sysconfdir}/%{name}/
%{__install} -m 0644 %{name}.logrotate %{buildroot}%{_sysconfdir}/logrotate.d/%{name}
%{__install} -m 0644 %{name}.service %{buildroot}%{_unitdir}/

%pre
getent group %{daemon_group} >/dev/null || groupadd -r %{daemon_group}
getent passwd %{daemon_user} >/dev/null || \
    useradd -r -g %{daemon_group} -s /sbin/nologin -c "%{name} service account" %{daemon_user}
exit 0

%post
%systemd_post %{name}.service

%preun
%systemd_preun %{name}.service

%postun
%systemd_postun_with_restart %{name}.service

%files
%config(noreplace) %attr(-, root, %{daemon_group}) %{_sysconfdir}/%{name}/%{name}.ini
%config(noreplace) %{_sysconfdir}/logrotate.d/%{name}
%dir %attr(-, %{daemon_user}, %{daemon_group}) %{_localstatedir}/log/%{name}
%dir %attr(-, %{daemon_user}, %{daemon_group}) %{_localstatedir}/spool/%{name}
%doc README.rst
%license LICENSE
%{_bindir}/%{name}
%{_unitdir}/%{name}.service
%{python3_sitelib}/*

%changelog
%{lua:
    data = io.open('README.rst'):read('*a')
    changelog = data:match('\nChangelog\n=========\n\n.-\n\n(.+)$')
    heading_pattern = rex.newPOSIX([[([0-9]+\.[0-9]+\.[0-9]+) - ([0-9]{4}-[0-9]{2}-[0-9]{2})]] .. '\n-{18}\n\n')

    -- Find all of the changelog sections. Get the version, date, and start of the section body.
    sections = {}
    function callback (entire_matched_str, parsed_table)
        section_start = changelog:find(entire_matched_str, 0, true)
        body_start = section_start + #entire_matched_str
        version, date = unpack(parsed_table)
        year, month, day = date:match('(%d+)-(%d+)-(%d+)')
        date_hr = os.date('%a %b %d %Y', os.time{year=year, month=month, day=day})
        sections[#sections + 1] = {version, date_hr, section_start, body_start, #changelog, ''}
    end
    heading_pattern:gmatch(changelog, callback)

    -- Now find the end of each section body (right before the next section's heading).
    for i, section in pairs(sections) do
        if i < #sections then
            section[5] = sections[i + 1][3] - 1
        end
    end

    -- Next parse each section body.
    for _, section in pairs(sections) do
        body_start, body_end = unpack(section, 4, 5)
        raw_body = changelog:sub(body_start - 1, body_end)
        for k in raw_body:gmatch('(\n[^A-Z\n][^\n]+)') do
            section[6] = section[6] .. k:gsub('\n    ', '\n'):gsub('\n** ', '\n- ')
        end
    end

    -- Finally print each section.
    for _, section in pairs(sections) do
        version, date, _, _, _, body = unpack(section)
        print(string.format('* %s Robpol86 <robpol86@gmail.com> - %s-1%s\n\n', date, version, body))
    end
}
