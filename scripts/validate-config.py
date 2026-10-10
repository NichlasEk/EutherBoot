#!/usr/bin/env python3
"""Host-side validator for the proposed schema; not the firmware parser."""
import pathlib, sys, tomllib

def validate(c):
    def require(condition, message):
        if not condition: raise ValueError(message)
    require(set(c) == {'boot', 'entry'}, 'Expected only [boot] and [[entry]]')
    b, entries = c['boot'], c['entry']
    require(isinstance(b, dict) and set(b) == {'default','timeout','theme'}, 'boot requires default, timeout, theme; unknown keys forbidden')
    require(type(b['timeout']) is int and 0 <= b['timeout'] <= 3600, 'boot.timeout must be an integer in 0..3600; zero disables automatic boot')
    require(b['theme'] == 'system-regis', 'Unknown boot.theme')
    require(isinstance(b['default'], str), 'boot.default must be a string')
    require(isinstance(entries, list) and len(entries) > 0, 'At least one entry is required')
    ids = set()
    for i,e in enumerate(entries):
        require(isinstance(e,dict), f'entry {i}: expected table')
        kind=e.get('type')
        require(kind in ('efi','firmware'), f'entry {i}: unknown type')
        keys={'id','name','type'} | ({'path'} if kind == 'efi' else set())
        require(set(e) == keys, f'entry {i}: missing or unknown fields')
        require(all(isinstance(v,str) and v and not any(ord(ch)<32 for ch in v) for v in e.values()), f'entry {i}: fields must be nonempty strings without control characters')
        require(e['id'] not in ids, f'entry {i}: duplicate id')
        ids.add(e['id'])
        if kind == 'efi':
            path=e['path']
            require(path.startswith('\\EFI\\') and path.lower().endswith('.efi') and '/' not in path and ':' not in path and all(part not in ('','.','..') for part in path[1:].split('\\')), f'entry {i}: expected absolute EFI path without traversal')
    require(b['default'] in ids, 'boot.default must identify an existing entry')

if __name__ == '__main__':
    try:
        path=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else 'eutherboot.toml')
        validate(tomllib.loads(path.read_text()))
    except (ValueError, OSError) as error:
        sys.exit(f'Invalid configuration: {error}')
    print('Configuration proposal valid (host-side only)')
