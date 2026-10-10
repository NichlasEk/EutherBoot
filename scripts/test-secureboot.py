#!/usr/bin/env python3
"""Bounded Secure Boot matrix; each case generates independent throwaway keys."""
import argparse
from pathlib import Path
import os
import signal
import subprocess
import sys

p = argparse.ArgumentParser()
p.add_argument('--uki', action='store_true', help='Include signed diagnostic UKI (requires Linux fixtures)')
a = p.parse_args()
runner = Path(__file__).with_name('secureboot-qemu.py')
cases = [[], ['--width', '640', '--height', '480']]
if a.uki:cases.append(['--uki'])
failed = False
for args in cases:
    with subprocess.Popen([sys.executable, str(runner), *args], stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=True, start_new_session=True) as proc:
        try:output, _ = proc.communicate(timeout=200)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGINT)
            try:output, _ = proc.communicate(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL);output, _ = proc.communicate()
            output += '\nSecure Boot case exceeded 200 seconds\n'
            failed = True
        print(output, end='', flush=True)
        failed |= proc.returncode != 0
sys.exit(1 if failed else 0)
