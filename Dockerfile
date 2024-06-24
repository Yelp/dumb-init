ARG BASE_IMAGE=debian:buster
FROM $BASE_IMAGE

LABEL maintainer="Chris Kuehl <ckuehl@yelp.com>"

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
        python3-distutils \
        python3-setuptools \
        python3-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /tmp/mnt

COPY debian/control /control
RUN : \
    && apt-get update \
    && mk-build-deps --install --tool 'apt-get -y --no-install-recommends' /control \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
