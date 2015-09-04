FROM debian:jessie

MAINTAINER Chris Kuehl <ckuehl@yelp.com>
RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential devscripts equivs procps psmisc libpcre3 && \
    apt-get clean
WORKDIR /mnt

ENTRYPOINT mk-build-deps -i && make builddeb
