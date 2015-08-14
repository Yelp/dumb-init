dumb-init
========

[![Build Status](https://travis-ci.org/Yelp/dumb-init.svg?branch=master](https://travis-ci.org/Yelp/dumb-init) [![PyPI version](https://badge.fury.io/py/dumb-init.svg)](https://pypi.python.org/pypi/dumb-init)


`dumb-init` is a simple process designed to run as PID 1 inside Docker
containers and proxy signals to a single child process.

In Docker containers, a process typically runs as PID 1, which means that
signals like TERM will just bounce off your process unless it goes out of its
way to handle them (see the "Why" section below). This is a big problem with
scripts in languages like Python, Bash, or Ruby, and can lead to leaking Docker
containers if you're not careful.


## Why you need a signal proxy

Normally, when processes are sent a signal like `TERM`, the Linux kernel will
try to trigger any custom handlers the process has registered for that signal.

If the process hasn't registered custom handlers, the kernel will fall back to
default behavior for that signal (such as killing the process, in the case of
`TERM`).

However, processes which run as PID 1 get special treatment by the kernel, and
default signal handlers won't be applied. If your process doesn't explicitly
handle these signals, a `TERM` will have no effect at all.

For example, if you have Jenkins jobs that do `docker run my-container script`,
sending TERM to the `docker run` process will typically kill the `docker run`
command, but leave the container running in the background.


## What `dumb-init` does

`dumb-init` runs as PID 1, acting like a simple init system. It launches a
single process, and then proxies all received signals to that child process.

Since your actual process is no longer PID 1, when it receives signals from
`dumb-init`, the default signal handlers will be applied, and your process will
behave as you would expect.

If your process dies, `dumb-init` will also die.


## Installing inside Docker containers

You have a few options for using `dumb-init`:


### Option 1: Installing via an internal apt server

If you have an internal apt server, uploading the `.deb` to your server is the
recommended way to use `dumb-init`. In your Dockerfiles, you can simply
`apt-get install dumb-init` and it will be available.


### Option 2: Installing the `.deb` package manually

If you don't have an internal apt server, you can use `dpkg -i` to install the
`.deb` package. You can choose how you get the `.deb` onto your container
(mounting a directory or `wget`-ing it are some options).


### Option 3: Installing from PyPI

dumb-init can be installed [from PyPI](https://pypi.python.org/pypi/dumb-init)
using pip. Since dumb-init is written in C, you'll want to first install a C compiler
(on Debian/Ubuntu, `apt-get install gcc` is sufficient), then just `pip install
dumb-init`.


## Usage

Once installed inside your Docker container, simply prefix your commands with
`dumb-init`. For example:

    $ docker run my_container dumb-init python -c 'while True: pass'

Running this same command without `dumb-init` would result in being unable to
stop the container without SIGKILL, but with `dumb-init`, you can send it more
humane signals like TERM.


## See also

* [Docker and the PID 1 zombie reaping problem (Phusion Blog)](https://blog.phusion.nl/2015/01/20/docker-and-the-pid-1-zombie-reaping-problem/)
* [Trapping signals in Docker containers (@gchudnov)](https://medium.com/@gchudnov/trapping-signals-in-docker-containers-7a57fdda7d86)
* [pgctl](https://github.com/Yelp/pgctl)
