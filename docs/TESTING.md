# Verification — 2026-11-25

Device: POCO X7 Pro, Android 15, ARM64. Testing ran on the phone without a desktop mirror. Game and launcher were force-stopped after testing.

| Check | Result |
|---|---|
| All 29 dubbing RPF and 2 update RPF on the device match canonical v6 hashes | PASS |
| Compact installer reconstructs all 31 outputs from clean source files | PASS, final SHA-256 matches |
| APK signature, ZIP CRC and zipalign checks, both variants | PASS |
| Original core libgtav bytes preserved in both variants | PASS |
| Normal: launch, calibration, Persian A confirmation, gameplay | PASS |
| Normal: Persian pause/navigation captions and menu touch | PASS |
| Trainer: launch, gameplay, Persian menu with engine: ok | PASS after libshv repair |
| Trainer: process remains alive after menu interaction | PASS |
| Credits wording includes AmirPhpDeveloper, mobeegame and «استار کنید» | PASS |
| Later dismisses, returns next launch; Never persists across restart | PASS |
| Original launcher collage with Persian badge in jet-ski panel | Rendered through Android PackageManager |
| Encrypted RAR integrity, every part below 2 decimal GB | PASS |
| All final files copied to phone | See release delivery record |
| Every mission / every dialogue / every trainer feature | NOT fully tested |
| Actual Skip Cutscene action in a skippable scene | NOT independently tested |
| Voices-only runtime with a stock APK in this round | INCOMPLETE; stock installation was blocked |

Localization-only and combined data components use disjoint paths. Reconstruction and hashing were tested for both components; this is not a claim of exhaustive device coverage of every combination. The audio is the corrected v6 payload whose sample was previously confirmed audible by the user. No audio was re-encoded for compact distribution.

## Native trainer repair

The observed crash returned into libshv near offset 0x1dfa8. It called engine offset 0x176e148, which was inside a different command in the supplied engine. The proper `CommandClearPedTasksImmediately(int)` entry was 0x176ddfc. Related fixed addresses and benchmark null checks were validated against symbols/instructions in that exact trainer engine. Ten patch sites were changed, without changing libgtav itself. `source/reports/trainer-native-repair.json` records the precise changes.

This fix is specific to the recorded original binaries. A different game update requires fresh symbol/prologue validation. The previous v9/v10 experimental script changes are not included.

## Manual follow-up

Exercise a genuinely skippable cutscene, later missions, shops, phone calls, vehicle selection and each trainer action. Check both ordinary and trainer variants on more devices. Report exact reproduction steps and a sanitized crash report; avoid sharing private savedata or account details.
