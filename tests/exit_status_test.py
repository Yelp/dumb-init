from subprocess import Popen


def test_exit_status(both_debug_modes, both_pgroup_modes):
    """dumb-init should exit with the same exit status as the process that it
    supervises.
    """
    for status in [0, 1, 2, 32, 64, 127, 254, 255]:
        proc = Popen(('dumb-init', 'sh', '-c', 'exit {0}'.format(status)))
        proc.wait()
        assert proc.returncode == status
