"""Configuration fixtures and integration assertions for the real OVMF runner."""
import shutil
import time

ERRORS = {
    'config-missing': 'Config read: NOT_FOUND',
    'malformed': 'TOML line',
    'unknown': 'unknown field',
    'duplicate': 'duplicate id',
    'bad-default': 'boot.default does not identify an entry',
    'traversal': 'expected absolute',
    'utf8': 'Config is not UTF-8',
    'oversize': 'Config read: BAD_BUFFER_SIZE',
    'self': 'Configuration points to EutherBoot itself',
}
CASES = ('sample', 'default', 'timeout', 'cancel', 'timeout-missing', 'many', *ERRORS)


def prepare(esp, root, case):
    source = (root/'eutherboot.toml').read_text()
    destination = esp/'EFI/EutherBoot/eutherboot.toml'
    if case == 'sample':
        destination.write_text(source)
        return
    if case in ERRORS:
        source = source.replace('timeout = 0', 'timeout = 1')
        if case == 'config-missing':
            return
        if case == 'malformed':
            source += '\n[unfinished'
        elif case == 'unknown':
            source = source.replace('timeout = 1', 'timeout = 1\nunknown = true')
        elif case == 'duplicate':
            source += "\n[[entry]]\nid='test'\nname='Duplicate'\ntype='efi'\npath='\\EFI\\Duplicate.efi'\n"
        elif case == 'bad-default':
            source = source.replace('default = "test"', 'default = "does-not-exist"')
        elif case == 'traversal':
            source = source.replace('\\EFI\\EutherBoot\\TestChild.efi', '\\EFI\\..\\TestChild.efi')
        elif case == 'utf8':
            destination.write_bytes(b'\xff\xfe' + source.encode())
            return
        elif case == 'oversize':
            source += ' ' * (16*1024)
        elif case == 'self':
            source = source.replace('\\EFI\\EutherBoot\\TestChild.efi', '\\EFI\\BOOT\\BOOTX64.EFI')
        destination.write_text(source)
        return
    # Remove the old fixed target: successful loading must use the TOML path.
    (esp/'EFI/EutherBoot/TestChild.efi').unlink(missing_ok=True)
    (esp/'EFI/Alternate').mkdir()
    if case != 'timeout-missing':
        shutil.copy2(root/'artifacts/TestChild.efi', esp/'EFI/Alternate/Chosen.efi')
    count = 16 if case == 'many' else 2
    default = 'entry0' if case == 'many' else 'entry1'
    timeout = 3 if case in ('timeout', 'cancel', 'timeout-missing') else 0
    source = f'[boot]\ndefault="{default}"\ntimeout={timeout}\n'
    for i in range(count):
        name = f'Configured entry {i+1}'
        path = '\\EFI\\Alternate\\Chosen.efi' if i == count-1 else f'\\EFI\\Missing{i}.efi'
        source += f'\n[[entry]]\nid="entry{i}"\nname="{name}"\ntype="efi"\npath=\'{path}\'\n'
    destination.write_text(source)


def run(case, out, log, screen, key, wait_marker, width, height, menu_ready_at):
    def snapshot(name):
        screen(name)
        return (out/f'{name}.ppm').read_bytes().split(b'\n', 3)[3]

    if case in ERRORS:
        current = log.read_text()
        assert 'CONFIG_ERROR' in current and ERRORS[case] in current, current
        assert 'CONFIG_OK' not in current and 'TIMEOUT_ARMED' not in current
        snapshot('config-error')
        key('ret', 'CONFIG_INSPECT')
        assert ERRORS[case] in (out/'serial.log').read_text()
        time.sleep(1.5)  # Invalid fixtures request 1s: prove they cannot boot.
        assert 'CHAINLOAD_REQUEST' not in log.read_text()
        key('down', 'SELECT 1')
        key('ret', 'EXIT_FIRMWARE')
        return

    assert 'CONFIG_OK' in log.read_text()
    assert f'MENU_READY selected={0 if case == "many" else 1}' in log.read_text()
    first = snapshot('configured-menu')
    assert first.count(bytes((8, 21, 35))) > width*height//2
    if case == 'many':
        for index in range(1,16):
            key('down', f'SELECT {index}')
        page = snapshot('last-page')
        assert page != first
        key('ret', 'CHILD_READY')
        assert 'CHAINLOAD_REQUEST id=entry15 path=\\EFI\\Alternate\\Chosen.efi' in log.read_text()
        key('ret', 'MENU_RESUMED')
        key('down', 'SELECT 16')
        key('ret', 'CONFIG_INSPECT')
        assert '16 entries. Default: entry0' in (out/'serial.log').read_text()
        key('down', 'SELECT 17')
        key('ret', 'EXIT_FIRMWARE')
        return
    if case == 'cancel':
        key('x', 'TIMEOUT_CANCELLED')  # Even an otherwise unhandled key cancels.
        time.sleep(3.5)
        assert 'CHAINLOAD_REQUEST' not in log.read_text() and 'TIMEOUT_FIRED' not in log.read_text()
        key('ret', 'CHILD_READY')
    elif case in ('timeout', 'timeout-missing'):
        wait_marker('TIMEOUT_FIRED', 0)
        elapsed = time.monotonic() - menu_ready_at
        assert 2.5 <= elapsed <= 10, f'3s timeout fired at {elapsed:.2f}s'
        if case == 'timeout-missing':
            wait_marker('MENU_RESUMED', 0)
            assert 'CHAINLOAD_ERROR Load(NOT_FOUND)' in log.read_text()
            time.sleep(3.5)
            assert log.read_text().count('CHAINLOAD_REQUEST') == 1
            assert 'CHILD_STARTED' not in log.read_text()
            snapshot('timeout-failure')
            key('esc', 'EXIT_FIRMWARE')
            return
        wait_marker('CHILD_READY', 0)
    else:
        assert 'TIMEOUT_ARMED' not in log.read_text()
        key('ret', 'CHILD_READY')
    snapshot('configured-child')
    key('ret', 'MENU_RESUMED')
    current = log.read_text()
    assert 'CHAINLOAD_REQUEST id=entry1 path=\\EFI\\Alternate\\Chosen.efi' in current
    assert 'CHAINLOAD_REQUEST id=entry0' not in current
    assert 'CHILD_CONTEXT_OK' in current and 'CHAINLOAD_RETURN_SUCCESS' in current
    returned = snapshot('configured-return')
    assert first[:(height-110)*width*3] == returned[:(height-110)*width*3]
    if case == 'timeout':
        time.sleep(3.5)
        assert log.read_text().count('TIMEOUT_FIRED') == 1
        assert log.read_text().count('CHAINLOAD_REQUEST') == 1
    key('down', 'SELECT 2')
    key('ret', 'CONFIG_INSPECT')
    assert '2 entries. Default: entry1' in (out/'serial.log').read_text()
    key('down', 'SELECT 3')
    key('ret', 'EXIT_FIRMWARE')
