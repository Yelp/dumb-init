FROM debian:jessie

MAINTAINER Chris Kuehl <ckuehl@yelp.com>
RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential devscripts equivs musl-tools python python-pytest python-mock && \
    rm -rf /var/lib/apt/lists/* && apt-get clean
WORKDIR /mnt

ENTRYPOINT mk-build-deps -i --tool 'apt-get --no-install-recommends -y' && make builddeb
