import os

collect_ignore = []
if os.name == 'nt':
    collect_ignore.append('tests/test_async.py')
    collect_ignore.append('tests/test_interact.py')