"""Serial guest oracles: no shared folders or host-side shell evaluation."""
import re
import uuid
import time

def drain(serial):
    try:
        while serial.recv(65536):pass
    except OSError:pass

def wait(v,pattern,before=0,timeout=180):
    deadline=time.monotonic()+timeout
    while True:
        log=(v.base/'serial.log').read_text(errors='replace')[before:]
        if match:=re.search(pattern,log):return match
        if v.proc.poll() is not None or time.monotonic()>deadline:
            raise AssertionError(f'Missing {pattern}: {log[-3500:]}')
        time.sleep(.1)

def command(v,serial,script,timeout=180):
    marker=uuid.uuid4().hex
    before=len((v.base/'serial.log').read_text(errors='replace'))
    # A child shell gives set -e its normal semantics; completion is not terminal echo.
    import shlex
    line=f"bash -eu -o pipefail -c {shlex.quote(script)}; printf '\\nCOMMAND_{marker}=%s\\n' \"$?\"\n"
    serial.sendall(line.encode())
    result=wait(v,rf'(?m)^COMMAND_{marker}=(\d+)\r?$',before,timeout)
    log=(v.base/'serial.log').read_text(errors='replace')[before:]
    assert result.group(1)=='0',log[-5000:]
    return log
