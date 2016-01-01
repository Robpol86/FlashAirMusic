Name:           %{getenv:NAME}
Version:        %{getenv:VERSION}
Release:        1%{?dist}
Summary:        %{getenv:SUMMARY}
Group:          Development/Libraries

License:        MIT
URL:            %{getenv:URL}
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
Requires:       python3-docopt
Requires:       python3-PyYAML
Requires:       python3-requests

%description
=============
FlashAirMusic
=============

Sync FLAC music to your car's head unit using a FlashAir WiFi SD card.

.. image:: https://img.shields.io/travis/Robpol86/FlashAirMusic/master.svg?style=flat-square&label=Travis%20CI
    :target: https://travis-ci.org/Robpol86/FlashAirMusic
    :alt: Build Status

.. image:: https://img.shields.io/coveralls/Robpol86/FlashAirMusic/master.svg?style=flat-square&label=Coveralls
    :target: https://coveralls.io/github/Robpol86/FlashAirMusic
    :alt: Coverage Status

.. image:: https://img.shields.io/github/release/Robpol86/FlashAirMusic.svg?style=flat-square&label=Latest
    :target: https://github.com/Robpol86/FlashAirMusic/releases
    :alt: Latest Version

.. image:: https://img.shields.io/github/downloads/Robpol86/FlashAirMusic.svg?style=flat-square&label=Downloads
    :target: https://github.com/Robpol86/FlashAirMusic/releases
    :alt: Downloads

%prep
%autosetup -n %{name}-%{version}

%build
%py3_build

%install
%py3_install

%check
%{__python3} setup.py test

%files
%license LICENSE
%doc README.rst
%{python3_sitelib}/*
%{_bindir}/%{name}
