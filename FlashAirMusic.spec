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
    description = string.match(data, '^=+\n' .. name .. '\n=+\n\n(.-)\n\n.. image::')
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
