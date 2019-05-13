import os
import pty
import re
import signal
import termios
import time

import pytest


EOF = b'\x04'


def ttyflags(fd):
    """normalize tty i/o for testing"""
    # see:
    # http://www.gnu.org/software/libc/manual/html_mono/libc.html#Output-Modes
    attrs = termios.tcgetattr(fd)
    attrs[1] &= ~termios.OPOST  # don't munge output
    attrs[3] &= ~termios.ECHO  # don't echo input
    termios.tcsetattr(fd, termios.TCSANOW, attrs)


def readall(fd):
    """read until EOF"""
    result = b''
    while True:
        try:
            chunk = os.read(fd, 1 << 10)
        except OSError as error:
            if error.errno == 5:  # linux pty EOF
                return result
            else:
                raise
        if chunk == b'':
            return result
        else:
            result += chunk


# disable debug output so it doesn't break our assertion
@pytest.mark.usefixtures('debug_disabled')
def test_tty():
    """Ensure processes under dumb-init can write successfully, given a tty."""
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp('dumb-init', ('dumb-init', 'tac'))
    else:
        # write to tac via the pty and verify its output
        ttyflags(fd)
        assert os.write(fd, b'1\n2\n3\n') == 6
        assert os.write(fd, EOF * 2) == 2
        output = readall(fd)
        assert os.waitpid(pid, 0) == (pid, 0)

        assert output == b'3\n2\n1\n', repr(output)


@pytest.mark.usefixtures('both_debug_modes')
@pytest.mark.usefixtures('both_setsid_modes')
def test_child_gets_controlling_tty_if_we_had_one():
    """If dumb-init has a controlling TTY, it should give it to the child.

    To test this, we make a new TTY then exec "dumb-init bash" and ensure that
    the shell has working job control.
    """
    pid, sfd = pty.fork()
    if pid == 0:
        os.execvp('dumb-init', ('dumb-init', 'bash', '-m'))
    else:
        ttyflags(sfd)

        # We might get lots of extra output from the shell, so print something
        # we can match on easily.
        assert os.write(sfd, b'echo "flags are: [[$-]]"\n') == 25
        assert os.write(sfd, b'exit 0\n') == 7
        output = readall(sfd)
        assert os.waitpid(pid, 0) == (pid, 0), output

        m = re.search(b'flags are: \\[\\[([a-zA-Z]+)\\]\\]\n', output)
        assert m, output

        # "m" is job control
        flags = m.group(1)
        assert b'm' in flags


def test_sighup_sigcont_ignored_if_was_session_leader():
    """The first SIGHUP/SIGCONT should be ignored if dumb-init is the session leader.

    Due to TTY quirks (#136), when dumb-init is the session leader and forks,
    it needs to avoid forwarding the first SIGHUP and SIGCONT to the child.
    Otherwise, the child might receive the SIGHUP post-exec and terminate
    itself.

    You can "force" this race by adding a `sleep(1)` before the signal handling
    loop in dumb-init's code, but it's hard to reproduce the race reliably in a
    test otherwise. Because of this, we're stuck just asserting debug messages.
    """
    pid, fd = pty.fork()
    if pid == 0:
        # child
        os.execvp('dumb-init', ('dumb-init', '-v', 'sleep', '20'))
    else:
        # parent
        ttyflags(fd)

        # send another SIGCONT to make sure only the first is ignored
        time.sleep(0.5)
        os.kill(pid, signal.SIGHUP)

        output = readall(fd).decode('UTF-8')

        assert 'Ignoring tty hand-off signal {}.'.format(signal.SIGHUP) in output
        assert 'Ignoring tty hand-off signal {}.'.format(signal.SIGCONT) in output

        assert '[dumb-init] Forwarded signal {} to children.'.format(signal.SIGHUP) in output
        assert '[dumb-init] Forwarded signal {} to children.'.format(signal.SIGCONT) not in output
