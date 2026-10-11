#!/usr/bin/env python3
"""Guest-only unauthenticated TUI probe. Never run against a personal Codex home."""
import os,pty,select,time,signal,sys,fcntl,termios,struct
assert not os.path.exists(os.path.expanduser('~/.codex/auth.json')), 'Use a disposable rescue guest'
pid,fd=pty.fork()
if pid==0:
    os.environ['TERM']='xterm-256color'
    os.execvp(sys.argv[1],sys.argv[1:])
fcntl.ioctl(fd,termios.TIOCSWINSZ,struct.pack('HHHH',30,100,0,0))
output=b''
try:
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        if select.select([fd],[],[],.2)[0]:
            try: chunk=os.read(fd,65536)
            except OSError:break
            if not chunk:break
            output+=chunk
            if b'\x1b[6n' in output[-100:]:os.write(fd,b'\x1b[1;1R')
            if b'\x1b[c' in chunk:os.write(fd,b'\x1b[?1;2c')
            if b'\x1b]10;?' in chunk:os.write(fd,b'\x1b]10;rgb:ffff/ffff/ffff\x1b\\')
            if b'\x1b]11;?' in chunk:os.write(fd,b'\x1b]11;rgb:0000/0000/0000\x1b\\')
            if b'Sign in' in output or b'Welcome to Codex' in output:break
finally:
    try:os.kill(pid,signal.SIGTERM)
    except ProcessLookupError:pass
    time.sleep(.2)
    try:os.kill(pid,signal.SIGKILL)
    except ProcessLookupError:pass
    os.waitpid(pid,0)
    os.close(fd)
print(output.decode(errors='replace'))
if b'Sign in' in output or b'Welcome to Codex' in output:print('CODEX_ONBOARDING_REACHED')
else:
    print('CODEX_ONBOARDING_NOT_REACHED')
    sys.exit(1)
