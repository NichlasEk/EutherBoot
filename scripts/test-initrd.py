#!/usr/bin/env python3
"""Bounded LoadFile2 protocol/lifetime matrix using a synthetic returning consumer."""
import concurrent.futures
from pathlib import Path
import os
import signal
import subprocess
import sys
runner=Path(__file__).with_name('initrd-qemu.py')
cases=[['--case',name] for name in ('return','install','cleanup','old-stub','empty','none')]
cases += [['--case',name,'--width','640','--height','480'] for name in ('return','cleanup')]
def run(args):
    with subprocess.Popen([sys.executable,str(runner),*args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True) as proc:
        try:output,_=proc.communicate(timeout=200)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGINT)
            try:output,_=proc.communicate(timeout=8)
            except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);output,_=proc.communicate()
            return 1,output+'\nLoadFile2 case exceeded 200 seconds\n'
        return proc.returncode,output
failed=False
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    for status,output in pool.map(run,cases):
        print(output,end='',flush=True)
        failed |= status!=0
sys.exit(1 if failed else 0)
