dumb-init
========

[![PyPI version](https://badge.fury.io/py/dumb-init.svg)](https://pypi.python.org/pypi/dumb-init)


**dumb-init** is a simple process supervisor and init system designed to run as
PID 1 inside minimal container environments (such as [Docker][docker]). It is
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
[session](http://man7.org/linux/man-pages/man2/setsid.2.html) rooted at the
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


### Signal rewriting

dumb-init allows rewriting incoming signals before proxying them. This is
useful in cases where you have a Docker supervisor (like Mesos or Kubernetes)
which always sends a standard signal (e.g. SIGTERM). Some apps require a
different stop signal in order to do graceful cleanup.

For example, to rewrite the signal SIGTERM (number 15) to SIGQUIT (number 3),
just add `--rewrite 15:3` on the command line.

To drop a signal entirely, you can rewrite it to the special number `0`.


#### Signal rewriting special case

When running in setsid mode, it is not sufficient to forward
`SIGTSTP`/`SIGTTIN`/`SIGTTOU` in most cases, since if the process has not added
a custom signal handler for these signals, then the kernel will not apply
default signal handling behavior (which would be suspending the process) since
it is a member of an orphaned process group. For this reason, we set default
rewrites to `SIGSTOP` from those three signals. You can opt out of this
behavior by rewriting the signals back to their original values, if desired.

One caveat with this feature: for job control signals (`SIGTSTP`, `SIGTTIN`,
`SIGTTOU`), dumb-init will always suspend itself after receiving the signal,
even if you rewrite it to something else.


## Installing inside Docker containers

You have a few options for using `dumb-init`:


### Option 1: Installing from your distro's package repositories (Debian, Ubuntu, etc.)

Many popular Linux distributions (including Debian (since `stretch`) and Debian
derivatives such as Ubuntu (since `bionic`)) now contain dumb-init packages in
their official repositories.

On Debian-based distributions, you can run `apt install dumb-init` to install
dumb-init, just like you'd install any other package.

*Note:* Most distro-provided versions of dumb-init are not statically-linked,
unlike the versions we provide (see the other options below). This is normally
perfectly fine, but means that these versions of dumb-init generally won't work
when copied to other Linux distros, unlike the statically-linked versions we
provide.


### Option 2: Installing via an internal apt server (Debian/Ubuntu)

If you have an internal apt server, uploading the `.deb` to your server is the
recommended way to use `dumb-init`. In your Dockerfiles, you can simply
`apt install dumb-init` and it will be available.

Debian packages are available from the [GitHub Releases tab][gh-releases], or
you can run `make builddeb` yourself.


### Option 3: Installing the `.deb` package manually (Debian/Ubuntu)

If you don't have an internal apt server, you can use `dpkg -i` to install the
`.deb` package. You can choose how you get the `.deb` onto your container
(mounting a directory or `wget`-ing it are some options).

One possibility is with the following commands in your Dockerfile:

```Dockerfile
RUN wget https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_amd64.deb
RUN dpkg -i dumb-init_*.deb
```


### Option 4: Downloading the binary directly

Since dumb-init is released as a statically-linked binary, you can usually just
plop it into your images. Here's an example of doing that in a Dockerfile:

```Dockerfile
RUN wget -O /usr/local/bin/dumb-init https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_x86_64
RUN chmod +x /usr/local/bin/dumb-init
```


### Option 5: Installing from PyPI

Though `dumb-init` is written entirely in C, we also provide a Python package
which compiles and installs the binary. It can be installed [from
PyPI](https://pypi.python.org/pypi/dumb-init) using `pip`. You'll want to first
install a C compiler (on Debian/Ubuntu, `apt-get install gcc` is sufficient),
then just `pip install dumb-init`.

As of 1.2.0, the package at PyPI is available as a pre-built wheel archive and does not
need to be compiled on common Linux distributions.


## Usage

Once installed inside your Docker container, simply prefix your commands with
`dumb-init` (and make sure that you're using [the recommended JSON
syntax][docker-cmd-json]).

Within a Dockerfile, it's a good practice to use dumb-init as your container's
entrypoint. An "entrypoint" is a partial command that gets prepended to your
`CMD` instruction, making it a great fit for dumb-init:

```Dockerfile
# Runs "/usr/bin/dumb-init -- /my/script --with --args"
ENTRYPOINT ["/usr/bin/dumb-init", "--"]

# or if you use --rewrite or other cli flags
# ENTRYPOINT ["dumb-init", "--rewrite", "2:3", "--"]

CMD ["/my/script", "--with", "--args"]
```

If you declare an entrypoint in a base image, any images that descend from it
don't need to also declare dumb-init. They can just set a `CMD` as usual.

For interactive one-off usage, you can just prepend it manually:

    $ docker run my_container dumb-init python -c 'while True: pass'

Running this same command without `dumb-init` would result in being unable to
stop the container without `SIGKILL`, but with `dumb-init`, you can send it
more humane signals like `SIGTERM`.

It's important that you use [the JSON syntax][docker-cmd-json] for `CMD` and
`ENTRYPOINT`. Otherwise, Docker invokes a shell to run your command, resulting
in the shell as PID 1 instead of dumb-init.


### Using a shell for pre-start hooks

Often containers want to do some pre-start work which can't be done during
build time. For example, you might want to template out some config files based
on environment variables.

The best way to integrate that with dumb-init is like this:

```Dockerfile
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["bash", "-c", "do-some-pre-start-thing && exec my-server"]
```

By still using dumb-init as the entrypoint, you always have a proper init
system in place.

The `exec` portion of the bash command is important because it [replaces the
bash process][exec] with your server, so that the shell only exists momentarily
at start.


## Building dumb-init

Building the dumb-init binary requires a working compiler and libc headers and
defaults to glibc.

    $ make


### Building with musl

Statically compiled dumb-init is over 700KB due to glibc, but musl is now an
option. On Debian/Ubuntu `apt-get install musl-tools` to install the source and
wrappers, then just:

    $ CC=musl-gcc make

When statically compiled with musl the binary size is around 20KB.


### Building the Debian package

We use the standard Debian conventions for specifying build dependencies (look
in `debian/control`). An easy way to get started is to `apt-get install
build-essential devscripts equivs`, and then `sudo mk-build-deps -i --remove`
to install all of the missing build dependencies automatically. You can then
use `make builddeb` to build dumb-init Debian packages.

If you prefer an automated Debian package build using Docker, just run `make
builddeb-docker`. This is easier, but requires you to have Docker running on
your machine.


## See also

* [Docker and the PID 1 zombie reaping problem (Phusion Blog)](https://blog.phusion.nl/2015/01/20/docker-and-the-pid-1-zombie-reaping-problem/)
* [Trapping signals in Docker containers (@gchudnov)](https://medium.com/@gchudnov/trapping-signals-in-docker-containers-7a57fdda7d86)
* [tini](https://github.com/krallin/tini), an alternative to dumb-init
* [pid1](https://github.com/fpco/pid1), an alternative to dumb-init, written in Haskell


[daemontools]: http://cr.yp.to/daemontools.html
[docker-cmd-json]: https://docs.docker.com/engine/reference/builder/#run
[docker]: https://www.docker.com/
[exec]: https://en.wikipedia.org/wiki/Exec_(system_call)
[gh-releases]: https://github.com/Yelp/dumb-init/releases
[supervisord]: http://supervisord.org/
[systemd]: https://wiki.freedesktop.org/www/Software/systemd/
[sysvinit]: https://wiki.archlinux.org/index.php/SysVinit
