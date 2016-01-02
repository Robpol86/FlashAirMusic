BuildArch:      noarch
BuildRequires:  python3-devel
Group:          Development/Libraries
License:        MIT
Name:           %{getenv:NAME}
Release:        1%{?dist}
Requires:       python3-docopt
Requires:       python3-PyYAML
Requires:       python3-requests
Source0:        %{name}-%{version}.tar.gz
Summary:        %{getenv:SUMMARY}
URL:            %{getenv:URL}
Version:        %{getenv:VERSION}

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
%py3_build

%install
%py3_install

%files
%license LICENSE
%doc README.rst
%{python3_sitelib}/*
%{_bindir}/%{name}

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
        sections[#sections + 1] = {version, date_hr, section_start, body_start, #changelog, nil}
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
        raw_body = changelog:sub(body_start, body_end):match("^%s*(.-)%s*$")
        section[6] = '- TODO'
    end

    -- Finally print each section.
    for _, section in pairs(sections) do
        version, date, _, _, _, body = unpack(section)
        print(string.format('* %s Robpol86 <robpol86@gmail.com> - %s-1\n%s\n\n', date, version, body))
    end
}
