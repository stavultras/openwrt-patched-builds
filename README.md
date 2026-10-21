# openwrt-patched-builds

Unofficial OpenWrt sysupgrade images for hardware-modified routers, built automatically
with the official ImageBuilder whenever a new OpenWrt stable release appears.

> [!WARNING]
> **Unofficial builds, use at your own risk.** These images are not made or supported by the
> OpenWrt project or by Cudy/netis. They are only for boards with the hardware modification
> described below. Flashing the wrong image, or any image on an unmodified board, can leave
> the router unbootable and need serial/recovery access to fix. Hardware modifications void
> the warranty. Everything here is provided "as is", without warranty of any kind; the author
> is not responsible for damaged devices or data loss.

| Image | Board | Modification | Patch |
|---|---|---|---|
| `*cudy_wr3000-v1-64mb-squashfs-sysupgrade.bin` | Cudy WR3000 v1 | 16 MB NOR replaced by 64 MB NOR | [patches/Cudy-WR3000-64MB-V1.patch](patches/Cudy-WR3000-64MB-V1.patch) |
| `*netis_nx32u-v2-squashfs-sysupgrade.itb` | netis NX30 V2 | USB port soldered (USB 2.0, VBUS on GPIO 14) | [patches/Netis-NX30U-v2.patch](patches/Netis-NX30U-v2.patch) |

Download images from [Releases](../../releases). **Only flash the image matching your mod.**

Images are stock OpenWrt plus LuCI (and `kmod-usb3` on the NX30). Attended Sysupgrade is
deliberately not included: it would install stock images and undo the hardware mods.
Upgrade with the next image from this repo instead (keep settings works as usual).

## How it works

`.github/workflows/build.yml` runs daily and, for every new stable release:

1. Checks that each patch in `patches/` still applies to that release's DTS (otherwise the build fails for review).
2. Applies the equivalent overlay from `overlays/` to the stock DTB in the ImageBuilder.
3. Rebuilds the kernel FIT if it embeds the DTB, raises `IMAGE_SIZE` where needed, and runs `make image`.
4. Verifies the final image contains the patched DTB and publishes a `vX.Y.Z` release.

A keepalive step re-enables the workflow on every scheduled run, so GitHub's
60-day inactivity rule does not switch the daily check off.

When you change a patch, update the matching overlay too. Run manually from the Actions tab
(optionally with a specific version and `force` to rebuild an existing release).

## License

Patches, overlays and workflow are licensed under [GPL-2.0](LICENSE), the same as OpenWrt.
The released images contain OpenWrt and are subject to its licenses; their sources are at
[github.com/openwrt/openwrt](https://github.com/openwrt/openwrt) (tag matching the release)
plus the patches in this repo.
