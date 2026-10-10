#!/usr/bin/env python3
"""Independent, bounded virtual tests; each has its own ESP and firmware copy."""
import concurrent.futures
import pathlib
import os
import signal
import subprocess
import sys
import qemu_cases
script = pathlib.Path(__file__).with_name('qemu.py')
cases = [[], ['--width','640','--height','480'], ['--disk-image']]
cases += [['--scenario',s] for s in ('abort','missing','invalid')]
cases += [['--config-case',s] for s in qemu_cases.CASES if s != 'sample']
# Exercise scrolling at the smallest supported framebuffer resolution.
cases += [['--config-case','many','--width','640','--height','480']]

cases = [(script, ['--test',*args]) for args in cases]
editor = script.with_name('editor-qemu.py')
cases += [(editor,['--case',case]) for case in ('discard','save','invalid','readonly','after-stage','after-backup','after-install')]
cases += [(editor,['--case','save','--width','640','--height','480'])]

def run(case):
    program, args = case
    with subprocess.Popen([sys.executable,str(program),*args],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, start_new_session=True) as proc:
        try:
            output, _ = proc.communicate(timeout=110)
            return args, proc.returncode, output
        except subprocess.TimeoutExpired:
            # Interrupt the whole isolated process group. Python gets a chance
            # to run the runner's finally block and clean temporary storage.
            os.killpg(proc.pid, signal.SIGINT)
            try:
                output, _ = proc.communicate(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                output, _ = proc.communicate()
            return args, 1, output + '\nTest exceeded 110 seconds\n'

failed = False
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    for args, status, output in pool.map(run,cases):
        print(output, end='', flush=True)
        if status:
            failed = True
            print(f'FAILED: {args}', flush=True)
sys.exit(1 if failed else 0)
