import os
import subprocess
import sys

# FIXME: Can-should we reference this value and get rid of version_hamster?
SCRIPT_VERS = '0.10.0'

def run_hamster_love():
    """Bash shim"""
    # This feels so dirty it feels so right.
    hamster_briefs_path = os.path.dirname(__file__)
    abspath = os.path.join(hamster_briefs_path, 'hamster_love.sh')
    p = subprocess.Popen([abspath,] + sys.argv[1:], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    while True:
        out = p.stdout.read(1).decode()
        if out == '' and p.poll() != None:
            break
        if out != '':
            sys.stdout.write(out)
            sys.stdout.flush()

