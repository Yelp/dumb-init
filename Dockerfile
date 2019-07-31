FROM debian:buster

LABEL maintainer="Chris Kuehl <ckuehl@yelp.com>"

# The default mirrors are too flaky to run reliably in CI.
RUN sed -E \
    '/security\.debian/! s@http://[^/]+/@http://mirrors.kernel.org/@' \
    -i /etc/apt/sources.list

# Install the bare minimum dependencies necessary for working with Debian
# packages. Build dependencies should be added under "Build-Depends" inside
# debian/control instead.
RUN : \
    && apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential \
        devscripts \
        equivs \
        lintian \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /tmp/mnt

COPY debian/control /control
RUN : \
    && apt-get update \
    && mk-build-deps --install --tool 'apt-get -y --no-install-recommends' /control \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENTRYPOINT make builddeb
