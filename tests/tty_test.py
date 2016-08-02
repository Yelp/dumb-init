import os
import pty
import termios

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


def _test(fd):
    """write to tac via the pty and verify its output"""
    ttyflags(fd)
    assert os.write(fd, b'1\n2\n3\n') == 6
    assert os.write(fd, EOF * 2) == 2
    output = readall(fd)
    assert output == b'3\n2\n1\n', repr(output)
    print('PASS')


# disable debug output so it doesn't break our assertion
@pytest.mark.usefixtures('debug_disabled')
def test_tty():
    """
    Ensure processes wrapped by dumb-init can write successfully, given a tty
    """
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp('dumb-init', ('dumb-init', 'tac'))
    else:
        _test(fd)
