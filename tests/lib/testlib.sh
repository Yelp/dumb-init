catchable_signals() {
    # We can't handle the signals SIGKILL=9, SIGCHLD=17, SIGSTOP=19
    seq 1 31 | grep -vE '^(9|17|19)$'
}
