#!/usr/bin/env python3
import copy, importlib.util, pathlib, tomllib, unittest
spec=importlib.util.spec_from_file_location('validator',pathlib.Path(__file__).with_name('validate-config.py'))
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
BASE=tomllib.loads((pathlib.Path(__file__).resolve().parent.parent/'eutherboot.toml').read_text())
class Validation(unittest.TestCase):
    def test_example(self): m.validate(BASE)
    def test_fail_closed(self):
        for field,value in [('default','missing'),('timeout',True),('timeout',-1),('theme','unknown'),('typo',1)]:
            with self.subTest(field=field,value=value):
                c=copy.deepcopy(BASE); c['boot'][field]=value
                with self.assertRaises(ValueError): m.validate(c)
    def test_duplicate(self):
        c=copy.deepcopy(BASE); c['entry']*=2
        with self.assertRaises(ValueError): m.validate(c)
    def test_traversal(self):
        c=copy.deepcopy(BASE); c['entry'][0].update(type='efi',path='\\EFI\\..\\bad.efi')
        with self.assertRaises(ValueError): m.validate(c)
unittest.main()
