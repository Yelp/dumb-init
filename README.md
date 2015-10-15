dumb-init
========

[![Circle CI](https://circleci.com/gh/Yelp/dumb-init.svg?style=svg)](https://circleci.com/gh/Yelp/dumb-init)
[![PyPI version](https://badge.fury.io/py/dumb-init.svg)](https://pypi.python.org/pypi/dumb-init)


`dumb-init` is a simple process supervisor and init system designed to run as
PID 1 inside minimal container environments (such as [Docker][docker]). It is a
deployed as a small, statically-linked binary written in C.

Lightweight containers have popularized the idea of running a single process or
service without normal init systems like [systemd][systemd] or
[sysvinit][sysvinit]. However, omitting an init system often leads to incorrect
handling of processes and signals, and can result in problems such as
containers which can't be gracefully stopped, or leaking containers which
should have been destroyed.

`dumb-init` enables you to simply prefix your command with `dumb-init`. It acts
as PID 1 and immediately spawns your command as a child process, taking care to
properly handle and forward signals as they are received.


## Why you need an init system

Normally, when you launch a Docker container, the process you're executing
becomes PID 1, giving it the quirks and responsibilities that come with being
the init system for the container.

There are two common issues this presents:

1. In most cases, signals won't be handled properly.

   The Linux kernel applies special signal handling to processes which run as
   PID 1.

   When processes are sent a signal on a normal Linux system, the kernel will
   first check for any custom handlers the process has registered for that
   signal, and otherwise fall back to default behavior (for example, killing
   the process on `SIGTERM`).

   However, if the process receiving the signal is PID 1, it gets special
   treatment by the kernel; if it hasn't registered a handler for the signal,
   the kernel won't fall back to default behavior, and nothing happens. In
   other words, if your process doesn't explicitly handle these signals,
   sending it `SIGTERM` will have no effect at all.

   A common example is CI jobs that do `docker run my-container script`: sending
   `SIGTERM` to the `docker run` process will typically kill the `docker run` command,
   but leave the container running in the background.

2. Orphaned zombie processes aren't properly reaped.

   A process becomes a zombie when it exits, and remains a zombie until its
   parent calls some variation of the `wait()` system call on it. It remains in
   the process table as a "defunct" process. Typically, a parent process will
   call `wait()` immediately and avoid long-living zombies.

   If a parent exits before its child, the child is "orphaned", and is
   re-parented under PID 1. The init system is thus responsible for
   `wait()`-ing on orphaned zombie processes.

   Of course, most processes *won't* `wait()` on random processes that happen
   to become attached to them, so containers often end with dozens of zombies
   rooted at PID 1.


## What `dumb-init` does

`dumb-init` runs as PID 1, acting like a simple init system. It launches a
single process and then proxies all received signals to a session rooted at
that child process.

Since your actual process is no longer PID 1, when it receives signals from
`dumb-init`, the default signal handlers will be applied, and your process will
behave as you would expect. If your process dies, `dumb-init` will also die,
taking care to clean up any other processes that might still remain.


### Session behavior

In its default mode, `dumb-init` establishes a
[session](http://man7.org/linux/man-pages/man2/setsid.2.html)) rooted at the
child, and sends signals to the entire process group. This is useful if you
have a poorly-behaving child (such as a shell script) which won't normally
signal its children before dying.

This can actually be useful outside of Docker containers in regular process
supervisors like [daemontools][daemontools] or [supervisord][supervisord] for
supervising shell scripts. Normally, a signal like `SIGTERM` received by a
shell isn't forwarded to subprocesses; instead, only the shell process dies.
With dumb-init, you can just write shell scripts with dumb-init in the shebang:

    #!/usr/bin/dumb-init /bin/sh
    my-web-server &  # launch a process in the background
    my-other-server  # launch another process in the foreground

Ordinarily, a `SIGTERM` sent to the shell would kill the shell but leave those
processes running (both the background and foreground!).  With dumb-init, your
subprocesses will receive the same signals your shell does.

If you'd like for signals to only be sent to the direct child, you can run with
the `--single-child` argument, or set the environment variable
`DUMB_INIT_SETSID=0` when running `dumb-init`. In this mode, dumb-init is
completely transparent; you can even string multiple together (like `dumb-init
dumb-init echo 'oh, hi'`).


## Installing inside Docker containers

You have a few options for using `dumb-init`:


### Option 1: Installing via an internal apt server (Debian/Ubuntu)

If you have an internal apt server, uploading the `.deb` to your server is the
recommended way to use `dumb-init`. In your Dockerfiles, you can simply
`apt-get install dumb-init` and it will be available.

Debian packages are available from the [GitHub Releases tab][gh-releases], or
you can run `make builddeb` yourself.


### Option 2: Installing the `.deb` package manually (Debian/Ubuntu)

If you don't have an internal apt server, you can use `dpkg -i` to install the
`.deb` package. You can choose how you get the `.deb` onto your container
(mounting a directory or `wget`-ing it are some options).

One possibility is with the following commands in your Dockerfile:

```bash
RUN wget https://github.com/Yelp/dumb-init/releases/download/v0.5.0/dumb-init_0.5.0_amd64.deb
RUN dpkg -i dumb-init_*.deb
```


### Option 3: Installing from PyPI

Though `dumb-init` is written entirely in C, we also provide a Python package
which compiles and installs the binary. It can be installed [from
PyPI](https://pypi.python.org/pypi/dumb-init) using pip. You'll want to first
install a C compiler (on Debian/Ubuntu, `apt-get install gcc` is sufficient),
then just `pip install dumb-init`.


## Usage

Once installed inside your Docker container, simply prefix your commands with
`dumb-init`. For example:

    $ docker run my_container dumb-init python -c 'while True: pass'

Running this same command without `dumb-init` would result in being unable to
stop the container without `SIGKILL`, but with `dumb-init`, you can send it
more humane signals like `SIGTERM`.


## See also

* [Docker and the PID 1 zombie reaping problem (Phusion Blog)](https://blog.phusion.nl/2015/01/20/docker-and-the-pid-1-zombie-reaping-problem/)
* [Trapping signals in Docker containers (@gchudnov)](https://medium.com/@gchudnov/trapping-signals-in-docker-containers-7a57fdda7d86)
* [pgctl](https://github.com/Yelp/pgctl)


[daemontools]: http://cr.yp.to/daemontools.html
[supervisord]: http://supervisord.org/
[gh-releases]: https://github.com/Yelp/dumb-init/releases
[systemd]: https://wiki.freedesktop.org/www/Software/systemd/
[sysvinit]: https://wiki.archlinux.org/index.php/SysVinit
[docker]: https://www.docker.com/
