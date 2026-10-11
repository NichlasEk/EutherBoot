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

class DualPublication(unittest.TestCase):
    def fixture(self, root):
        (root/'staging').mkdir()
        (root/'EFI/Linux').mkdir(parents=True)
        for p in ('linux', 'linux-lts'):
            (root/f'staging/{p}.efi').write_bytes(b'new-image')
            m.target_path({'esp':str(root)}, p).write_bytes(b'old')
        return {'esp':str(root), 'lts':True}

    def test_invalid_second_image_does_not_publish_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); c=self.fixture(root)
            with patch.object(m,'STATE',root), patch.object(m,'validate',side_effect=[None,RuntimeError('bad LTS')]), patch.object(m,'publish') as publish:
                with self.assertRaisesRegex(RuntimeError,'bad LTS'): m.publish_all(c)
                publish.assert_not_called()

    def test_accounts_for_growth_before_copying_either_image(self):
        from collections import namedtuple
        usage=namedtuple('Usage','total used free')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); c=self.fixture(root)
            # First image fits; its growth means the second would not.
            with patch.object(m,'STATE',root), patch.object(m,'validate'), patch.object(m,'MARGIN',4), patch.object(m.shutil,'disk_usage',return_value=usage(30,15,15)), patch.object(m,'publish') as publish:
                with self.assertRaisesRegex(RuntimeError,'Insufficient ESP'):m.publish_all(c)
                publish.assert_not_called()

    def test_symlink_second_image_does_not_publish_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); c=self.fixture(root)
            (root/'staging/linux-lts.efi').unlink()
            (root/'staging/linux-lts.efi').symlink_to(root/'staging/linux.efi')
            with patch.object(m,'STATE',root), patch.object(m,'validate'), patch.object(m,'publish') as publish:
                with self.assertRaisesRegex(RuntimeError,'regular staged'):m.publish_all(c)
                publish.assert_not_called()

if __name__=='__main__':unittest.main()
