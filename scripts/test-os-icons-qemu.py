#!/usr/bin/env python3
"""Exercise all icon masks in real menus, themes, pagination and display scales."""
import json,shutil,tempfile
from pathlib import Path
from PIL import Image
from qemu_test import VM
import virtual_disk
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'artifacts/icons/qemu';OUT.mkdir(parents=True,exist_ok=True)
(OUT/'result.json').unlink(missing_ok=True)
assets=ROOT/'crates/uefi-app/assets/icons'
icons=json.loads((assets/'manifest.json').read_text())['icons']
checks=[]
with tempfile.TemporaryDirectory(prefix='eutherboot-icons-') as temp:
    tmp=Path(temp)
    iteration=0
    for width,height,theme in [(1024,768,'system-regis'),(1024,768,'system-regis-light'),(1024,768,'high-contrast'),(640,480,'system-regis'),(1280,960,'system-regis')]:
        for offset in (0,16):
            iteration+=1;batch=icons[offset:offset+16]
            esp=tmp/f'esp-{iteration}';(esp/'EFI/BOOT').mkdir(parents=True);(esp/'EFI/EutherBoot').mkdir()
            shutil.copy2(ROOT/'artifacts/EutherBoot.efi',esp/'EFI/BOOT/BOOTX64.EFI')
            shutil.copy2(ROOT/'artifacts/TestChild.efi',esp/'EFI/EutherBoot/TestChild.efi')
            cfg=f"[boot]\ndefault='os0'\ntimeout=0\ntheme='{theme}'\n"
            for i,icon in enumerate(batch):
                shutil.copy2(ROOT/'artifacts/TestChild.efi',esp/f'EFI/EutherBoot/os{i}.efi')
                cfg+=f"\n[[entry]]\nid='os{i}'\nname='{icon['name'].replace(chr(39), '')}'\ntype='efi'\npath='\\EFI\\EutherBoot\\os{i}.efi'\n"
            (esp/'EFI/EutherBoot/eutherboot.toml').write_text(cfg)
            diskdir=tmp/f'disk-{iteration}';diskdir.mkdir();disk=virtual_disk.create(esp,diskdir)
            with VM(tmp,disk,OUT,iteration,width=width,height=height) as vm:
                assert 'CONFIG_ERROR' not in vm.log.read_text()
                scale=min(height//480,width//640,3);w=width//scale;h=height//scale
                visible=min(5,max(1,(w-80)//174));top=244 if h<600 else h//2+5
                for selected in range(len(batch)):
                    if selected:vm.key('right','GRAPHICS_READY')
                    if selected%visible:continue
                    vm.screen(f'page-{selected//visible}')
                    screenshot=Image.open(vm.base/f'page-{selected//visible}.ppm').convert('RGB')
                    screenshot.save(vm.base/f'page-{selected//visible}.png')
                    count=min(visible,len(batch)-selected);start=w//2-count*174//2+7
                    for slot,icon in enumerate(batch[selected:selected+count]):
                        mask=(assets/f"{icon['slug']}.alpha").read_bytes()
                        x=start+slot*174+50;y=top+6
                        solid=[n for n,a in enumerate(mask) if a==255]
                        assert len(solid)>20,icon['slug']
                        def pixel(n):return screenshot.getpixel(((x+n%64)*scale,(y+n//64)*scale))
                        color=pixel(solid[0])
                        assert all(pixel(n)==color for n in solid),(icon['slug'],'missing/wrong mask')
                        assert all(pixel(n)!=color for n,a in enumerate(mask) if a==0),(icon['slug'],'wrong silhouette')
                        if theme=='high-contrast':assert color==(255,255,255)
                        checks.append({'icon':icon['slug'],'theme':theme,'resolution':[width,height]})
                # A selected OS icon must still chainload and return normally.
                vm.key('ret','CHILD_READY');vm.key('ret','MENU_RESUMED')
                vm.screen('returned')
                vm.key('f2','TEXT_READY');vm.screen('text')
                print('PASS',theme,width,height,offset,flush=True)
(OUT/'result.json').write_text(json.dumps({'icon_checks':len(checks),'checks':checks,'chainload_return':True,'text_fallback':True,'host_disks_attached':False},indent=2)+'\n')
