#!/usr/bin/env python3
"""Full 128 MB NAND image for a Cudy WR3000 v1 with a 128 MB SPI-NAND
(ESMT F50L1G41LB), to write with a programmer on the first install.

Layout (WR3000S v1 ubootmod, the same as BL2/U-Boot/OpenWrt expect):
  0x000000  BL2         1 MB    bootloader/cudy-wr3000-128mb-nand-v1/*-preloader.bin
  0x100000  u-boot-env  512 KB  empty (the environment lives in UBI)
  0x180000  Factory     2 MB    your 64 KB Factory dump (Wi-Fi calibration)
  0x380000  bdinfo      256 KB  your 64 KB bdinfo dump (MAC addresses)
  0x3c0000  FIP         2 MB    bootloader/cudy-wr3000-128mb-nand-v1/*-bl31-uboot.fip
  0x5c0000  ubi         rest    empty, or OpenWrt preinstalled with --sysupgrade

Data only, no OOB (spare) area: write it with the chip's on-die ECC enabled
(the programmer's "without spare/OOB" mode), so the chip writes the ECC itself.

  wr3000-nand-dump.py --factory Factory.bin --bdinfo bdinfo.bin \\
      [--sysupgrade openwrt-...-cudy_wr3000-128mb-nand-v1-squashfs-sysupgrade.itb] \\
      -o wr3000-128mb-nand.bin
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
BOOT = os.path.join(HERE, '..', 'bootloader', 'cudy-wr3000-128mb-nand-v1')
FLASH = 128 << 20
PAGE, BLOCK = 2048, 128 << 10
PARTS = {  # name: (offset, size)
    'bl2': (0x000000, 0x100000),
    'factory': (0x180000, 0x200000),
    'bdinfo': (0x380000, 0x040000),
    'fip': (0x3c0000, 0x200000),
    'ubi': (0x5c0000, FLASH - 0x5c0000),
}


def default(suffix):
    names = [f for f in os.listdir(BOOT) if f.endswith(suffix)] if os.path.isdir(BOOT) else []
    return os.path.join(BOOT, names[0]) if len(names) == 1 else None


def ubi_image(sysupgrade, tmp):
    """UBI with the volumes U-Boot and OpenWrt sysupgrade would create."""
    ubinize = shutil.which('ubinize') or shutil.which('ubinize', path='/usr/sbin:/sbin')
    if not ubinize:
        sys.exit('ubinize not found (apt install mtd-utils)')
    cfg = os.path.join(tmp, 'ubinize.cfg')
    with open(cfg, 'w') as f:
        for i, name in enumerate(('ubootenv', 'ubootenv2')):
            f.write(f'[{name}]\nmode=ubi\nvol_id={i}\nvol_type=dynamic\nvol_name={name}\nvol_size=0x100000\n\n')
        f.write(f'[fit]\nmode=ubi\nvol_id=2\nvol_type=dynamic\nvol_name=fit\nimage={os.path.abspath(sysupgrade)}\n\n')
    out = os.path.join(tmp, 'ubi.bin')
    # fixed image sequence number keeps the output reproducible
    subprocess.run([ubinize, '-o', out, '-p', str(BLOCK), '-m', str(PAGE), '-s', str(PAGE),
                    '-Q', '0x57523030', cfg], check=True)
    return open(out, 'rb').read()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--factory', required=True, help='Factory dump (64 KB from the stock NOR, mtd2)')
    ap.add_argument('--bdinfo', required=True, help='bdinfo dump (64 KB from the stock NOR, mtd3)')
    ap.add_argument('--bl2', default=default('-preloader.bin'), help='BL2 (default: the one in bootloader/)')
    ap.add_argument('--fip', default=default('-bl31-uboot.fip'), help='FIP (default: the one in bootloader/)')
    ap.add_argument('--sysupgrade', help='preinstall this OpenWrt sysupgrade.itb in UBI '
                    '(without it U-Boot waits for the recovery image over TFTP)')
    ap.add_argument('-o', '--output', required=True)
    a = ap.parse_args()

    img = bytearray(b'\xff' * FLASH)
    files = {'bl2': a.bl2, 'factory': a.factory, 'bdinfo': a.bdinfo, 'fip': a.fip}
    for name, path in files.items():
        if not path:
            sys.exit(f'--{name} not given')
        data = open(path, 'rb').read()
        off, size = PARTS[name]
        if not data or len(data) > size:
            sys.exit(f'{path}: {len(data)} bytes, {name} holds up to {size}')
        img[off:off + len(data)] = data

    if open(a.bl2, 'rb').read(8) != b'SPINAND!':
        sys.exit(f'{a.bl2}: not an SPI-NAND BL2 (no SPINAND! header)')
    if open(a.fip, 'rb').read(4) != b'\x01\x00\x64\xaa':
        sys.exit(f'{a.fip}: not a FIP')
    if img[0x380000 + 0xde00:0x380000 + 0xde06] in (b'\xff' * 6, b'\x00' * 6):
        sys.exit(f'{a.bdinfo}: no MAC address at 0xde00, is it the bdinfo dump?')
    if img[0x180000:0x180002] not in (b'\x81\x79', b'\x79\x81'):
        print(f'warning: {a.factory} does not start with the MT7981 Wi-Fi EEPROM ID (0x7981)', file=sys.stderr)

    if a.sysupgrade:
        with tempfile.TemporaryDirectory() as tmp:
            ubi = ubi_image(a.sysupgrade, tmp)
        off, size = PARTS['ubi']
        if len(ubi) > size:
            sys.exit('UBI image too large')
        img[off:off + len(ubi)] = ubi

    with open(a.output, 'wb') as f:
        f.write(img)
    print(f'{a.output}: {FLASH >> 20} MB, MAC {img[0x380000 + 0xde00:0x380000 + 0xde06].hex(":")}'
          + (', OpenWrt preinstalled' if a.sysupgrade else ', UBI empty'))


if __name__ == '__main__':
    main()
