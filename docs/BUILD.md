# Building and maintaining

The release installer is standalone Python standard-library code. End-user installation does **not** require rebuilding an APK. Development scripts retain the validated Windows workspace layout; set up the external inputs below before running them. This is a source recipe for the recorded build, not a general APK translator.

## Required tools and external inputs

- Python 3.11, `fonttools`, `pillow`, `arabic-reshaper`, `python-bidi`.
- JDK 17, Android SDK platform 36 and build-tools 34.0.0, NDK 26.1.10909125, apktool 3.0.3, WinRAR RAR5.
- Original normal `game_android_final.apk` and trainer `game_android_final_signed by mohd saib.apk` at repository root. Use the exact supported builds; original libgtav hashes are in the APK verification report.
- GameSub font exported as `_patch_analysis/diagnostic/touch-ui/unicode-fonts-final/9_$Font2_Chalet-LondonNineteenSixty.ttf`. This proprietary input is not included.
- The matching Android fallback Arabic font as `_patch_analysis/apk_touch_fa/fallback-arabic.ttf`, with its original license.
- Clean original RPFs and the canonical corrected v6 outputs when regenerating compact patches. `build_compact.py` documents their expected `base`, `android_dub_work` and `full_patch_v6/patch_root` locations.

The scripts currently use `D:\Sdk`, `C:\Program Files\Java\jdk-17` and `C:\Program Files\WinRAR` paths. Adjust tool paths for your workstation. `FA_ICON_FONT` overrides the included OFL Vazirmatn Bold font. Keep signing keys private. The packager creates a dedicated key if none is supplied; it cannot reproduce the original publisher signature or the existing release signature without that key.

## APK recipe

1. Decode each original APK with apktool into `_patch_analysis/apk_touch_fa/normal` and `trainer`. Extract normal `assets/touch/atlas.bin` to `original-touch-atlas.bin`, normal `assets/hud/font.bin` to `original-font.bin`, trainer `lib/arm64-v8a/libshv.so` to `original-libshv.so`, and trainer libgtav to `trainer-original-libgtav.so` in the same work folder.
2. Dump the trainer engine's demangled symbols with the NDK `llvm-nm --demangle` into `trainer-symbols.txt`. Do not substitute another engine revision.
3. Run `build_ui.py`. This validates format placeholders, builds the Unicode GameSub font and Java helper, translates TextView/Canvas boundaries and installs launcher/format hooks. In-place String-to-CharSequence hooks are avoided because they can fail ART verification.
4. Run `build_native_ui.py`. It rebuilds the normal touch font atlas while preserving icon texels and generates the native translation shim. It validates exact engine prologues before runtime hook installation. Trainer uses the Java touch overlay path.
5. Run `repair_trainer.py`. Every old SHV instruction/data value is asserted before replacement. Do not remove these checks. The engine itself remains unchanged.
6. Run `build_icon_resource.py`. It compiles a layered drawable: original collage plus a vector Persian badge in the jet-ski panel.
7. Build the modified decoded projects with apktool as `normal-built.apk` and `trainer-built.apk`. `package_apks.py` takes their modified dex and adds the project's assets/helper into the original ZIP entries, updates labels and icon resources, aligns and signs both outputs. It verifies CRC, alignment, signature and unchanged-entry equality.
8. Test **both** final signed APKs on the target phone and repeat runtime tests whenever native addresses or rendering change. Passing a build alone is insufficient.

The original core libgtav is preserved byte-for-byte. Normal uses an added libfuzzyfa shim. Trainer intentionally changes libshv at the ten recorded sites. Original decoded APKs and extracted proprietary binaries are excluded from Git.

## Compact patches

`build_compact.py` produces manifests and ZIP payloads containing replacement/appended byte ranges. The installer copies unchanged ranges from verified original RPFs into a separate output, applies payloads, then verifies final SHA-256. It neither re-encodes audio nor modifies the source. Localization and dubbing have disjoint target paths.

`make_distribution.py` wraps the installer, manifests and payloads in password-protected RAR5 archives. It uses stored compression because ZIPs/APKs are already compressed. Dubbing volumes are 1800 MiB each, below 2 decimal GB. The localization RAR includes both fa APKs. Password is the public distribution password `mobeegame`.

When adapting these workspace scripts outside their original layout, point `PUBLIC` at the repository root and output at a separate release directory. Regenerate manifests only from matching source/target pairs. End-to-end reconstruction of all 31 files must pass before publishing new payloads.

## Scope

This repository contains integration scripts, helper Java/C++, translation tables, installer source, manifests and sanitized verification records. Proprietary game/translation inputs remain external. It does not recreate original voice performances or claim a new translation of every game string. See `THIRD_PARTY_NOTICES.md`.
