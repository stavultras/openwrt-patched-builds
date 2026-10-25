#!/usr/bin/env python3
"""Swap the DTB inside a prebuilt OpenWrt "uimage-lzma-loader" kernel.

ImageBuilder ships such kernels prebuilt (uImage -> lzma-loader -> LZMA(vmlinux + DTB))
and cannot rebuild the loader without a MIPS toolchain. The loader stops decoding at the
uncompressed size stored in the LZMA header, so a new stream can replace the old one in
place as long as it is not larger; the rest is zero-padded and the uImage CRCs updated.

  lzma-loader.py repack KERNEL_BIN VMLINUX DTB LZMA_TOOL
  lzma-loader.py contains IMAGE DTB
"""
import lzma
import os
import struct
import subprocess
import sys
import tempfile
import zlib

HDR = 64
# Build/lzma in OpenWrt first, then encoder settings that compress better (~2 KB here) in
# case the new stream comes out larger. The loader is built without _LZMA_OUT_READ, so it
# ignores the dictionary size and match finder; only lc/lp/pb must stay the same.
LZMA_ARGS = [['-lc1', '-lp2', '-pb2'],
             ['-lc1', '-lp2', '-pb2', '-d24'],
             ['-lc1', '-lp2', '-pb2', '-mfbt2', '-d24']]


def find_stream(buf, prefix):
    """Offset of the LZMA stream in buf whose output starts with prefix."""
    i = 0
    while (i := buf.find(b'\x6d\x00\x00', i)) >= 0:
        try:
            out = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE).decompress(buf[i:], max_length=len(prefix))
            if out == prefix:
                return i
        except lzma.LZMAError:
            pass
        i += 1
    sys.exit('LZMA stream not found')


def compress(data, tool, args):
    with tempfile.TemporaryDirectory() as d:
        src, dst = os.path.join(d, 'in'), os.path.join(d, 'out')
        open(src, 'wb').write(data)
        subprocess.run([tool, 'e', src, *args, dst], check=True, capture_output=True)
        return open(dst, 'rb').read()


def repack(kernel_bin, vmlinux, dtb, tool):
    k = bytearray(open(kernel_bin, 'rb').read())
    size = struct.unpack('>I', k[12:16])[0]
    payload = k[HDR:HDR + size]
    vm = open(vmlinux, 'rb').read()
    off = find_stream(bytes(payload), vm[:4096])
    room = size - off
    new = vm + open(dtb, 'rb').read()
    for args in LZMA_ARGS:
        z = compress(new, tool, args)
        print(f'lzma {" ".join(args)}: {len(z)} bytes, room {room}')
        if len(z) <= room:
            break
    else:
        sys.exit('new kernel+DTB does not fit into the lzma-loader')
    payload[off:] = z + bytes(room - len(z))
    assert lzma.LZMADecompressor(format=lzma.FORMAT_ALONE).decompress(bytes(payload[off:])) == new
    k[HDR:HDR + size] = payload
    k[24:28] = struct.pack('>I', zlib.crc32(payload))
    k[4:8] = bytes(4)
    k[4:8] = struct.pack('>I', zlib.crc32(k[:HDR]))
    open(kernel_bin, 'wb').write(k)
    print(f'{kernel_bin}: replaced DTB, stream at payload {off:#x}')


def contains(image, dtb):
    img = open(image, 'rb').read()
    d = open(dtb, 'rb').read()
    if d in img:
        return True
    i = 0
    while (i := img.find(b'\x6d\x00\x00', i, 8 << 20)) >= 0:
        try:
            if d in lzma.LZMADecompressor(format=lzma.FORMAT_ALONE).decompress(img[i:], max_length=64 << 20):
                return True
        except lzma.LZMAError:
            pass
        i += 1
    return False


if __name__ == '__main__':
    cmd, *args = sys.argv[1:]
    if cmd == 'repack':
        repack(*args)
    elif cmd == 'contains':
        sys.exit(0 if contains(*args) else 1)
    else:
        sys.exit(__doc__)
