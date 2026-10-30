# openwrt-patched-builds

Unofficial OpenWrt sysupgrade images for hardware-modified routers, built automatically
with the official ImageBuilder whenever a new OpenWrt stable release appears.

> [!WARNING]
> **Unofficial builds, use at your own risk.** These images are not made or supported by the
> OpenWrt project or by Cudy/netis/Xiaomi. They are only for boards with the hardware modification
> described below. Flashing the wrong image, or any image on an unmodified board, can leave
> the router unbootable and need serial/recovery access to fix. Hardware modifications void
> the warranty. Everything here is provided "as is", without warranty of any kind; the author
> is not responsible for damaged devices or data loss.

| Image | Board | Modification | Patch |
|---|---|---|---|
| `*cudy_wr3000-64mb-v1-squashfs-sysupgrade.bin` | Cudy WR3000 v1 | 16 MB NOR replaced by 64 MB NOR | [patches/Cudy-WR3000-64MB-V1.patch](patches/Cudy-WR3000-64MB-V1.patch) |
| `*cudy_wr3000-128mb-nand-v1-squashfs-sysupgrade.itb` | Cudy WR3000 v1 | 16 MB NOR replaced by 128 MB SPI-NAND (ESMT F50L1G41LB); OpenWrt BL2/U-Boot, [first install](#cudy-wr3000-v1-128-mb-nand-first-install) | [patches/Cudy-WR3000-128MB-NAND-V1.patch](patches/Cudy-WR3000-128MB-NAND-V1.patch) |
| `*netis_nx30-usb-v2-squashfs-sysupgrade.itb` | netis NX30 V2 | USB port soldered (USB 2.0, VBUS on GPIO 14) | [patches/Netis-NX30U-v2.patch](patches/Netis-NX30U-v2.patch) |
| `*xiaomi_mi-router-4a-gigabit-32mb-v2-squashfs-sysupgrade.bin` | Xiaomi Mi Router 4A Gigabit Edition v2 | 16 MB NOR replaced by 32 MB NOR; Breed or U-Boot | [patches/Xiaomi-R4A-Gigabit-32MB-V2.patch](patches/Xiaomi-R4A-Gigabit-32MB-V2.patch) |
| `*xiaomi_mi-router-4a-gigabit-64mb-v2-squashfs-sysupgrade.bin` | Xiaomi Mi Router 4A Gigabit Edition v2 | 16 MB NOR replaced by 64 MB NOR; U-Boot only (Breed doesn't support 64 MB) | [patches/Xiaomi-R4A-Gigabit-64MB-V2.patch](patches/Xiaomi-R4A-Gigabit-64MB-V2.patch) |

Download images from [Releases](../../releases). **Only flash the image matching your mod.**

Images are stock OpenWrt plus LuCI (and `kmod-usb3` on the NX30). Attended Sysupgrade is
deliberately not included: it would install stock images and undo the hardware mods.
Upgrade with the next image from this repo instead (keep settings works as usual).

## Cudy WR3000 v1 128 MB NAND: first install

The NAND board needs the OpenWrt bootloader, so the first install is a full NAND image
written with a programmer. Later upgrades are normal sysupgrades with
`*cudy_wr3000-128mb-nand-v1-squashfs-sysupgrade.itb`.

1. Before removing the NOR, back up the stock **Factory** (`mtd2`, Wi-Fi calibration) and
   **bdinfo** (`mtd3`, MAC addresses), 64 KB each. They are unique to your router.
2. Build the full 128 MB image from them (needs Python 3, and `ubinize` from mtd-utils
   for `--sysupgrade`):
   ```bash
   python3 scripts/wr3000-nand-dump.py --factory mtd2.Factory.bin --bdinfo mtd3.bdinfo.bin \
       --sysupgrade openwrt-X.Y.Z-mediatek-filogic-cudy_wr3000-128mb-nand-v1-squashfs-sysupgrade.itb \
       -o wr3000-128mb-nand.bin
   ```
   It holds BL2 and FIP from [`bootloader/cudy-wr3000-128mb-nand-v1`](bootloader/cudy-wr3000-128mb-nand-v1),
   your Factory and bdinfo, and OpenWrt preinstalled in UBI. Without `--sysupgrade` the UBI
   area is left empty; U-Boot then formats it and loads the recovery image over TFTP (step 4).
3. Write `wr3000-128mb-nand.bin` to the NAND **without the spare (OOB) area, with the chip's
   on-die ECC on** (the image is data only), and set the boot strap to SPI-NAND.
4. Recovery: U-Boot boots from TFTP when the UBI holds no system, or when reset is held
   at power-on. Set your PC to 192.168.1.254, serve
   `openwrt-mediatek-filogic-cudy_wr3000-128mb-nand-v1-initramfs-recovery.itb` (the release's
   `*-initramfs-recovery.itb`, renamed) over TFTP, then sysupgrade from the recovery system.

Layout (WR3000S v1 ubootmod): BL2 0x0, u-boot-env 0x100000, Factory 0x180000,
bdinfo 0x380000, FIP 0x3c0000, UBI 0x5c0000–end.
The image uses the `cudy_wr3000s-v1-ubootmod` profile (same NAND layout, BL2 and sysupgrade),
with the WR3000 v1 LEDs and 3 LAN ports in the DTB, so its board name is
`cudy,wr3000s-v1-ubootmod`. BL2 is the official OpenWrt `mt7981-cudy-ddr3` preloader;
the FIP is the official BL31 plus U-Boot built with
[`469-add-cudy_wr3000-v1-nand.patch`](bootloader/cudy-wr3000-128mb-nand-v1/469-add-cudy_wr3000-v1-nand.patch)
(`build.sh` in that folder rebuilds it).

## How it works

`.github/workflows/build.yml` runs daily and, for every new stable release:

1. Checks that each patch in `patches/` still applies to that release's DTS (otherwise the build fails for review).
2. Applies the equivalent overlay from `overlays/` to the stock DTB in the ImageBuilder.
3. Puts the patched DTB into the prebuilt kernel where it is embedded (rebuilds the FIT on filogic;
   on ramips swaps the compressed kernel+DTB inside the lzma-loader with `scripts/lzma-loader.py`),
   raises `IMAGE_SIZE` where needed, and runs `make image`.
4. Verifies the final image contains the patched DTB and publishes a `vX.Y.Z` release.
   For the WR3000 NAND board it also rebuilds the official `initramfs-recovery.itb` with the
   patched DTB (`scripts/recovery-fit.sh`), since ImageBuilder can't build initramfs images.

A keepalive step re-enables the workflow on every scheduled run, so GitHub's
60-day inactivity rule does not switch the daily check off.

When you change a patch, update the matching overlay too. Run manually from the Actions tab
(optionally with a specific version and `force` to rebuild an existing release).

## License

Patches, overlays and workflow are licensed under [GPL-2.0](LICENSE), the same as OpenWrt.
The released images contain OpenWrt and are subject to its licenses; their sources are at
[github.com/openwrt/openwrt](https://github.com/openwrt/openwrt) (tag matching the release)
plus the patches in this repo.
