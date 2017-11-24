import os

collect_ignore = []
if os.name == 'nt':
    collect_ignore.append('tests/test_async.py')
    collect_ignore.append('tests/test_ctrl_chars.py')
    collect_ignore.append('tests/test_destructor.py')
    collect_ignore.append('tests/test_dotall.py')
    collect_ignore.append('tests/test_expect.py')
    collect_ignore.append('tests/test_interact.py')