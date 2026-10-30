#!/bin/sh
# Rebuild the bootloader files in this folder (Debian/Ubuntu: apt install
# gcc-aarch64-linux-gnu bison flex swig python3-dev libssl-dev libgnutls28-dev
# device-tree-compiler u-boot-tools curl).
#
# BL2: the official OpenWrt mt7981-cudy-ddr3 preloader (SPI-NAND via SPIM,
#      DDR3, FIP at 0x3c0000), as shipped for the Cudy WR3000S v1 ubootmod.
# FIP: the official BL31 of the same release + U-Boot built from the OpenWrt
#      uboot-mediatek sources with 469-add-cudy_wr3000-v1-nand.patch
#      (the WR3000S v1 board with the WR3000 v1 LEDs and model name).
#
#   ./build.sh [OPENWRT_VERSION]
set -e
VER=${1:-25.12.6}
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$HERE
W=${WORKDIR:-$HERE/work}
BASE=https://downloads.openwrt.org/releases/$VER/targets/mediatek/filogic
SRC=openwrt-$VER-mediatek-filogic-cudy_wr3000s-v1-ubootmod
RAW=https://raw.githubusercontent.com/openwrt/openwrt/v$VER/package/boot/uboot-mediatek
NAME=openwrt-mediatek-filogic-cudy_wr3000-128mb-nand-v1

mkdir -p "$W" && cd "$W"

# official BL2 and FIP (for its BL31), sha256 checked
curl -fsSL "$BASE/sha256sums" -o sha256sums
for f in preloader.bin bl31-uboot.fip recovery.itb; do
	case $f in recovery.itb) f=initramfs-recovery.itb ;; esac
	[ -f "$SRC-$f" ] || curl -fsSLO "$BASE/$SRC-$f"
	grep " \*$SRC-$f\$" sha256sums | sha256sum -c
done
cp "$SRC-preloader.bin" "$OUT/$NAME-preloader.bin"

# fiptool from the TF-A commit OpenWrt uses
TFA=$(curl -fsSL "https://raw.githubusercontent.com/openwrt/openwrt/v$VER/package/boot/arm-trusted-firmware-mediatek/Makefile" \
	| sed -n 's/^PKG_SOURCE_VERSION:=//p')
[ -d tf-a ] || git clone -q https://github.com/mtk-openwrt/arm-trusted-firmware.git tf-a
git -C tf-a checkout -q "$TFA"
make -s -C tf-a fiptool OPENSSL_DIR=/usr >/dev/null
FIPTOOL=$PWD/tf-a/tools/fiptool/fiptool
mkdir -p fip-official && "$FIPTOOL" unpack --force --out fip-official "$SRC-bl31-uboot.fip"

# U-Boot: version and patches from the OpenWrt package of this release
UBVER=$(curl -fsSL "$RAW/Makefile" | sed -n 's/^PKG_VERSION:=//p')
UBHASH=$(curl -fsSL "$RAW/Makefile" | sed -n 's/^PKG_HASH:=//p')
[ -f "u-boot-$UBVER.tar.bz2" ] || curl -fsSLO "https://ftp.denx.de/pub/u-boot/u-boot-$UBVER.tar.bz2"
echo "$UBHASH  u-boot-$UBVER.tar.bz2" | sha256sum -c
rm -rf "u-boot-$UBVER" && tar xjf "u-boot-$UBVER.tar.bz2"
gh api "repos/openwrt/openwrt/contents/package/boot/uboot-mediatek/patches?ref=v$VER" -q '.[].name' > patches.list \
	|| curl -fsSL "https://api.github.com/repos/openwrt/openwrt/contents/package/boot/uboot-mediatek/patches?ref=v$VER" \
		| sed -n 's/.*"name": "\(.*\)".*/\1/p' > patches.list
mkdir -p patches
for p in $(cat patches.list); do
	[ -f "patches/$p" ] || curl -fsSL "$RAW/patches/$p" -o "patches/$p"
	patch -d "u-boot-$UBVER" -p1 -s < "patches/$p"
done
patch -d "u-boot-$UBVER" -p1 -s < "$HERE/469-add-cudy_wr3000-v1-nand.patch"

# the build time of the release (from its recovery image), for reproducible output
export SOURCE_DATE_EPOCH=$(fdtget -t u "$SRC-initramfs-recovery.itb" / timestamp)
make -s -C "u-boot-$UBVER" CROSS_COMPILE=aarch64-linux-gnu- mt7981_cudy_wr3000-v1-nand_defconfig
make -s -C "u-boot-$UBVER" -j"$(nproc)" CROSS_COMPILE=aarch64-linux-gnu- LOCALVERSION="-OpenWrt-$VER"

"$FIPTOOL" create --soc-fw fip-official/soc-fw.bin --nt-fw "u-boot-$UBVER/u-boot.bin" "$OUT/$NAME-bl31-uboot.fip"
"$FIPTOOL" info "$OUT/$NAME-bl31-uboot.fip"
cd "$OUT" && sha256sum "$NAME-preloader.bin" "$NAME-bl31-uboot.fip" > sha256sums && cat sha256sums
