dumb-init
========

[![Circle CI](https://circleci.com/gh/Yelp/dumb-init.svg?style=svg)](https://circleci.com/gh/Yelp/dumb-init) [![PyPI version](https://badge.fury.io/py/dumb-init.svg)](https://pypi.python.org/pypi/dumb-init)


`dumb-init` is a simple process designed to run as PID 1 inside Docker
containers and proxy signals to child processes.

In Docker containers, a process typically runs as PID 1, which means that
signals like TERM will just bounce off your process unless it goes out of its
way to handle them (see the "Why" section below). This is a big problem with
scripts in languages like Python, Ruby, or Bash, and can lead to leaking Docker
containers if you're not careful.


## Why you need a signal proxy

When processes are sent a signal on a normal Linux system, the kernel will
first check for any custom handlers the process has registered for that signal,
and otherwise fall back to default behavior (for example, killing the process
on `TERM`).

However, if the process receiving the signal is PID 1, it gets special
treatment by the kernel; if it hasn't registered a handler for the signal, the
kernel won't fall back to default behavior, and nothing happens. In other
words, if your process doesn't explicitly handle these signals, a `TERM` will
have no effect at all.

A common example is CI jobs that do `docker run my-container script`: sending
TERM to the `docker run` process will typically kill the `docker run` command,
but leave the container running in the background.


## What `dumb-init` does

`dumb-init` runs as PID 1, acting like a simple init system. It launches a
single process, and then proxies all received signals to that child process.

Since your actual process is no longer PID 1, when it receives signals from
`dumb-init`, the default signal handlers will be applied, and your process will
behave as you would expect. If your process dies, `dumb-init` will also die.


### Process group behavior

In its default mode, `dumb-init` establishes a process group (and "session",
via [setsid(2)](http://man7.org/linux/man-pages/man2/setsid.2.html)) rooted at
the child, and sends signals to the entire process group. This is useful if you
have a poorly-behaving child (such as a shell script) which won't normally
signal its children before dying.

This can actually be useful outside of Docker containers in regular process
supervisors like [daemontools][daemontools] or [supervisord][supervisord] for
supervising shell scripts. Normally, a signal like SIGTERM received by a shell
isn't forwarded to subprocesses; instead, only the shell process dies. With
dumb-init, you can just write shell scripts with dumb-init in the shebang:

    #!/usr/bin/dumb-init /bin/sh
    my-web-server &  # launch a process in the background
    my-other-server  # launch another process in the foreground

Ordinarily, a TERM sent to the shell would leave those processes running. With
dumb-init, your subprocesses will receive the same signals your shell does.

If you'd like for signals to only be sent to the direct child, you can set the
environment variable `DUMB_INIT_SETSID=0` when running `dumb-init`. In this
mode, dumb-init is completely transparent; you can even string multiple
together (like `dumb-init dumb-init echo 'oh, hi'`).


## Installing inside Docker containers

You have a few options for using `dumb-init`:


### Option 1: Installing via an internal apt server

If you have an internal apt server, uploading the `.deb` to your server is the
recommended way to use `dumb-init`. In your Dockerfiles, you can simply
`apt-get install dumb-init` and it will be available.

Debian packages are available from the [GitHub Releases tab][gh-releases], or
you can run `make builddeb` yourself.


### Option 2: Installing the `.deb` package manually

If you don't have an internal apt server, you can use `dpkg -i` to install the
`.deb` package. You can choose how you get the `.deb` onto your container
(mounting a directory or `wget`-ing it are some options).

One possibility is with the following commands in your Dockerfile:

```bash
RUN wget https://github.com/Yelp/dumb-init/releases/download/v0.3.1/dumb-init_0.3.1_amd64.deb
RUN dpkg -i dumb-init_*.deb
```


### Option 3: Installing from PyPI

dumb-init can be installed [from PyPI](https://pypi.python.org/pypi/dumb-init)
using pip. Since dumb-init is written in C, you'll want to first install a C
compiler (on Debian/Ubuntu, `apt-get install gcc` is sufficient), then just
`pip install dumb-init`.


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


[daemontools]: http://cr.yp.to/daemontools.html
[supervisord]: http://supervisord.org/
[gh-releases]: https://github.com/Yelp/dumb-init/releases
