"""Prune policy tests on temporary files; never inspect a real ESP or generation."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('ctl',ROOT/'tools/eutherbootctl.py')
ctl=importlib.util.module_from_spec(spec);spec.loader.exec_module(ctl)

class GenerationGuards(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name);self.state=root/'state';self.state.mkdir()
        self.esp=root/'esp';self.target=self.esp/'EFI/EutherBoot';self.target.mkdir(parents=True)
        (self.target/'.installation-id').write_text('test\n')
        self.generation='linux-test-generation'
        self.archive=self.state/'generations'/self.generation;self.archive.mkdir(parents=True)
        (self.archive/'modules').mkdir();(self.archive/'modules/retained').write_bytes(b'module fixture')
        self.manifest=self.state/'installation.json'
        self.manifest.write_text(json.dumps({'esp':str(self.esp),'guid':'test-guid','id':'test'}))
        self.args=SimpleNamespace(esp=self.esp,esp_guid='test-guid',generation=self.generation,apply=False)
        for name,value in [('STATE',self.state),('MANIFEST',self.manifest)]:
            patcher=patch.object(ctl,name,value);patcher.start();self.addCleanup(patcher.stop)
        patcher=patch.object(ctl,'esp_check');patcher.start();self.addCleanup(patcher.stop)
    def call(self):
        with contextlib.redirect_stdout(io.StringIO()):ctl.prune(self.args)
    def test_plan_leaves_files_unchanged(self):
        self.call();self.assertEqual((self.archive/'modules/retained').read_bytes(),b'module fixture')
    def test_apply_removes_only_unreferenced_generation(self):
        kernels=self.target/'kernels';kernels.mkdir()
        image=kernels/f'recovery-{self.generation}.efi';image.write_bytes(b'obsolete')
        active=kernels/'linux.efi';active.write_bytes(b'current')
        self.args.apply=True
        # Redirect only the process lock; file removals and filesystem syncs are real.
        import builtins
        with patch.object(ctl,'open',create=True,side_effect=lambda path,mode:builtins.open(self.state/'test.lock',mode)):
            self.call()
        self.assertFalse(self.archive.exists());self.assertFalse(image.exists())
        self.assertEqual(active.read_bytes(),b'current')
    def test_selected_recovery_is_retained(self):
        (self.state/'linux-previous').write_text(self.generation+'\n')
        with self.assertRaisesRegex(RuntimeError,'selected recovery'):self.call()
        self.assertTrue(self.archive.exists())
    def test_pending_transaction_is_retained(self):
        (self.state/'pending').mkdir();(self.state/'pending/linux').write_text(self.generation+'\n')
        with self.assertRaisesRegex(RuntimeError,'pending transaction'):self.call()
    def test_editor_backup_reference_is_retained(self):
        (self.target/'eutherboot.toml.bak').write_text(f"path='\\EFI\\EutherBoot\\kernels\\recovery-{self.generation}.efi'\n")
        with self.assertRaisesRegex(RuntimeError,'referenced by configuration'):self.call()
    def test_path_escape_is_rejected(self):
        self.args.generation='../installation.json'
        with self.assertRaisesRegex(RuntimeError,'Invalid generation'):self.call()
    def test_symlink_archive_is_rejected(self):
        other=self.state/'outside';self.archive.rename(other);self.archive.symlink_to(other)
        with self.assertRaisesRegex(RuntimeError,'symbolic-link'):self.call()
    def test_wrong_installation_is_rejected(self):
        (self.target/'.installation-id').write_text('other\n')
        with self.assertRaisesRegex(RuntimeError,'identity mismatch'):self.call()

if __name__=='__main__':unittest.main()
