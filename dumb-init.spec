Name:           dumb-init
Version:        1.1.3
Release:        1%{?dist}
Summary:        Entry-point for containers that proxies signals

License:        MIT
URL:            https://github.com/Yelp/dumb-init
Source0:        https://github.com/Yelp/dumb-init/archive/v1.1.3.tar.gz

BuildRequires:  vim-common
BuildRequires:  help2man

%description
dumb-init is a simple process supervisor and init system designed to run as
PID 1 inside minimal container environments (such as Docker).

* It can handle orphaned zombie processes.
* It can pass signals properly for simple containers.

%prep
%setup -q 

%build

# if we are building a release then this is not needed
# make VERSION.h 
gcc -std=gnu99 %{optflags} -o %{name} dumb-init.c 
help2man --no-discard-stderr --include debian/help2man --no-info --name '%{summary}' ./%{name} | gzip -9 > %{name}.1.gz


%install
rm -rf $RPM_BUILD_ROOT
mkdir -p "${RPM_BUILD_ROOT}/%{_bindir}" "${RPM_BUILD_ROOT}/%{_mandir}/man1/"
cp %{name} "${RPM_BUILD_ROOT}/%{_bindir}/"
cp %{name}.1.gz "${RPM_BUILD_ROOT}/%{_mandir}/man1/"

%files
%{_bindir}/%{name}
%license LICENSE
%doc README.md
%doc %{_mandir}/man1/%{name}.1.gz


%changelog
* Mon Aug 15 2016 alsadi <alsadi@gmail.com> - 1.1.3-1
- initial packaging
