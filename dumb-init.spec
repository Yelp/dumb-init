Name:           dumb-init
Version:        1.1.3
Release:        3%{?dist}
Summary:        Entry-point for containers that proxies signals

License:        MIT
URL:            https://github.com/Yelp/dumb-init
Source0:        https://github.com/Yelp/dumb-init/archive/v%{version}.tar.gz

# /bin/xxd of vim-common of is needed for non-released versions
# BuildRequires:  vim-common
BuildRequires:  help2man

%description
dumb-init is a simple process supervisor and init system designed to run as
PID 1 inside minimal container environments (such as Docker).

* It can handle orphaned zombie processes.
* It can pass signals properly for simple containers.

%prep
%setup -q 

%build
# uncomment next line when building a non-released version
# make VERSION.h 
gcc -std=gnu99 %{optflags} -o %{name} dumb-init.c 
help2man --no-discard-stderr --include debian/help2man --no-info --name '%{summary}' ./%{name} | gzip -9 > %{name}.1.gz

%install
mkdir -p "${RPM_BUILD_ROOT}/%{_bindir}" "${RPM_BUILD_ROOT}/%{_mandir}/man1/"
install -pm 755 %{name} "${RPM_BUILD_ROOT}/%{_bindir}/"
install -pm 644 %{name}.1.gz "${RPM_BUILD_ROOT}/%{_mandir}/man1/"

%files
%{_bindir}/%{name}
%license LICENSE
%doc README.md
%{_mandir}/man1/%{name}.1.gz

%changelog
* Wed Aug 17 2016 Muayyad Alsadi <alsadi@gmail.com> - 1.1.3-3
- remove vim-common and use install

* Mon Aug 15 2016 Muayyad Alsadi <alsadi@gmail.com> - 1.1.3-2
- initial packaging
