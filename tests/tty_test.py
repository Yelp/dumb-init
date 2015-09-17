import os


EOF = b'\x04'


def ttyflags(fd):
    """normalize tty i/o for testing"""
    # see:
    # http://www.gnu.org/software/libc/manual/html_mono/libc.html#Output-Modes
    import termios as T
    attrs = T.tcgetattr(fd)
    attrs[1] &= ~T.OPOST  # don't munge output
    attrs[3] &= ~T.ECHO  # don't echo input
    T.tcsetattr(fd, T.TCSANOW, attrs)


def tac():
    """
    run tac. if it fails to complete in 1 second send SIGKILL and exit with an
    error.
    """
    from os import execvp
    execvp('timeout', ('timeout', '1', 'dumb-init', 'tac'))


def readall(fd):
    """read until EOF"""
    from os import read
    result = b''
    while True:
        try:
            chunk = read(fd, 1 << 10)
        except OSError as error:
            if error.errno == 5:  # linux pty EOF
                return result
            else:
                raise
        if chunk == '':
            return result
        else:
            result += chunk


def _test(fd):
    """write to tac via the pty and verify its output"""
    ttyflags(fd)
    from os import write
    assert write(fd, b'1\n2\n3\n') == 6
    assert write(fd, EOF * 2) == 2
    output = readall(fd)
    assert output == b'3\n2\n1\n', repr(output)
    print('PASS')


def test_tty():
    """
    Ensure processes wrapped by dumb-init can write successfully, given a tty
    """
    # disable debug output so it doesn't break our assertion
    os.environ['DUMB_INIT_DEBUG'] = '0'
    import pty
    pid, fd = pty.fork()
    if pid == 0:
        tac()
    else:
        _test(fd)
