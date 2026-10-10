"""Budget tests with sparse synthetic payloads, including a large GPU initramfs."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('ctl_capacity',ROOT/'tools/eutherbootctl.py')
ctl=importlib.util.module_from_spec(spec);spec.loader.exec_module(ctl)
MIB=1024**2

class Capacity(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
    def payloads(self,initrd_mib):
        for package in ('linux','linux-lts'):
            for name,size in [(f'vmlinuz-{package}',17*MIB),(f'initramfs-{package}.img',initrd_mib*MIB)]:
                with (self.root/name).open('wb') as f:f.truncate(size)
    def test_large_initramfs_refuses_host_sized_free_space(self):
        self.payloads(257)
        self.assertGreater(ctl.arch_capacity(self.root),419*MIB)
        self.assertGreater(ctl.arch_capacity(self.root),1024*MIB)
    def test_small_payload_budget_fits_virtual_esp(self):
        self.payloads(20)
        self.assertLess(ctl.arch_capacity(self.root),950*MIB)
        self.assertGreater(ctl.arch_capacity(self.root),3*(2*(17+20))*MIB)
    def test_missing_lts_payload_is_not_zero_sized(self):
        self.payloads(20);(self.root/'initramfs-linux-lts.img').unlink()
        with self.assertRaisesRegex(RuntimeError,'Missing linux-lts'):ctl.arch_capacity(self.root)
    def test_actual_publication_size_preserves_active_target(self):
        active=self.root/'active.efi';active.write_bytes(b'known-good')
        candidate=self.root/'new.efi'
        with candidate.open('wb') as f:f.truncate(400*MIB)
        # Source the actual production functions, without its root-owned config
        # prologue. Firmware image identity and capacity are controlled oracles.
        common=(ROOT/'packaging/arch/common.sh').read_text()
        functions=self.root/'functions.sh';functions.write_text(common[common.index('fail()'):])
        result=subprocess.run(['bash','-c','''set -euo pipefail
source "$1"
bootctl() { echo uki; }
df() { printf 'Avail\\n%s\\n' 439353344; }
publish_file "$2" "$3"
''','test',str(functions),str(candidate),str(active)],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('insufficient ESP capacity for complete UKI staging',result.stderr)
        self.assertEqual(active.read_bytes(),b'known-good')
        self.assertEqual(list(self.root.glob('active.efi.new.*')),[])

if __name__=='__main__':unittest.main()
