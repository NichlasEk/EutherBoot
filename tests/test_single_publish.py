"""Faults during staging must preserve the active ESP file."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
spec=importlib.util.spec_from_file_location('single',Path(__file__).resolve().parents[1]/'tools/eutherboot-single.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Publication(unittest.TestCase):
    def test_partial_copy_and_rename_failure_preserve_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); target=root/'EFI/Linux/arch-normal.efi'
            target.parent.mkdir(parents=True);target.write_bytes(b'active')
            source=root/'staged.efi';source.write_bytes(b'new image')
            def broken_copy(src,dst):
                dst.write(b'partial')
                raise OSError('simulated I/O failure')
            for operation, replacement in [('copyfileobj',broken_copy),('replace',OSError('simulated rename failure'))]:
                with self.subTest(operation=operation), patch.object(m,'check'),patch.object(m,'validate'):
                    owner=m.shutil if operation=='copyfileobj' else m.os
                    with patch.object(owner,operation,side_effect=replacement):
                        with self.assertRaises(OSError):m.publish(source,{'esp':str(root)})
                self.assertEqual(target.read_bytes(),b'active')
                self.assertEqual(list(target.parent.iterdir()),[target])

if __name__=='__main__':unittest.main()
