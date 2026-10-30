#!/bin/sh
# Rebuild an official OpenWrt "initramfs-recovery.itb" (kernel-1 + initrd-1 +
# fdt-1, one configuration) with another DTB. Keeps the descriptions, load
# address and timestamp, so rebuilds are byte-identical.
#
#   recovery-fit.sh IN.itb DTB OUT.itb MKIMAGE
set -e
IN=$1 DTB=$2 OUT=$3 MKIMAGE=$4
W=$(mktemp -d)
trap 'rm -rf "$W"' EXIT

[ "$(fdtget -l "$IN" /images | tr '\n' ' ')" = "kernel-1 initrd-1 fdt-1 " ] || { echo "$IN: unexpected FIT images"; exit 1; }
[ "$(fdtget -t s "$IN" /images/kernel-1 compression)" = lzma ] || { echo "$IN: kernel is not lzma"; exit 1; }
dumpimage -T flat_dt -p 0 -o "$W/kernel" "$IN" >/dev/null
dumpimage -T flat_dt -p 1 -o "$W/initrd" "$IN" >/dev/null
cp "$DTB" "$W/fdt"

g() { fdtget -t s "$IN" "$@"; }
LOAD=$(printf '0x%08x' "$(fdtget -t u "$IN" /images/kernel-1 load)")
ENTRY=$(printf '0x%08x' "$(fdtget -t u "$IN" /images/kernel-1 entry)")
cat > "$W/fit.its" <<ITS
/dts-v1/;

/ {
	description = "$(g / description)";
	#address-cells = <1>;

	images {
		kernel-1 {
			description = "$(g /images/kernel-1 description)";
			data = /incbin/("$W/kernel");
			type = "kernel";
			arch = "$(g /images/kernel-1 arch)";
			os = "linux";
			compression = "lzma";
			load = <$LOAD>;
			entry = <$ENTRY>;
			hash-1 { algo = "crc32"; };
			hash-2 { algo = "sha1"; };
		};
		initrd-1 {
			description = "$(g /images/initrd-1 description)";
			data = /incbin/("$W/initrd");
			type = "ramdisk";
			arch = "$(g /images/initrd-1 arch)";
			os = "linux";
			hash-1 { algo = "crc32"; };
			hash-2 { algo = "sha1"; };
		};
		fdt-1 {
			description = "$(g /images/fdt-1 description)";
			data = /incbin/("$W/fdt");
			type = "flat_dt";
			arch = "$(g /images/fdt-1 arch)";
			compression = "none";
			hash-1 { algo = "crc32"; };
			hash-2 { algo = "sha1"; };
		};
	};

	configurations {
		default = "config-1";
		config-1 {
			description = "$(g /configurations/config-1 description)";
			kernel = "kernel-1";
			fdt = "fdt-1";
			ramdisk = "initrd-1";
		};
	};
};
ITS
SOURCE_DATE_EPOCH=$(fdtget -t u "$IN" / timestamp) "$MKIMAGE" -f "$W/fit.its" "$OUT" >/dev/null
# "pad-to 64k" as in OpenWrt
SIZE=$(stat -c %s "$OUT")
truncate -s $(( (SIZE + 65535) / 65536 * 65536 )) "$OUT"
