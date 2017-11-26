import os

collect_ignore = []
if os.name == 'nt':
    collect_ignore.append('tests/test_async.py')
    collect_ignore.append('tests/test_ctrl_chars.py')
    collect_ignore.append('tests/test_destructor.py')
    collect_ignore.append('tests/test_dotall.py')
    collect_ignore.append('tests/test_expect.py')
    collect_ignore.append('tests/test_interact.py')
    collect_ignore.append('tests/test_log.py')
    collect_ignore.append('tests/test_misc.py')
    collect_ignore.append('tests/test_performance.py')
    collect_ignore.append('tests/test_pxssh.py')
    collect_ignore.append('tests/test_run.py')
    collect_ignore.append('tests/test_socket.py')
    collect_ignore.append('tests/test_which.py')
    collect_ignore.append('tests/test_winsize.py')
