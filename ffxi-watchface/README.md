# Vana'diel Chronograph: FFXI watch face for Wear OS

A Pixel Watch / Wear OS watch face inspired by the Seiko × FINAL FANTASY XI
"WE ARE VANA'DIEL" 20th-anniversary chronograph. It's built with Google's
**Watch Face Format** (WFF), so it's an XML-and-images package with no app code.

| Active | Always-on |
|---|---|
| ![active](docs/preview_active.png) | ![ambient](docs/preview_ambient.png) |

## Design (after the Seiko piece)

| Seiko element | This face |
|---|---|
| Blue crystal index at 12 | Large faceted blue crystal with glow |
| "XI" at 11 | Gold serif **XI** |
| Crystal-shaped indices | Faceted silver crystals at 1, 2, 4, 5, 7, 8, 10 |
| Excalibur chronograph seconds hand | Sweeping Excalibur seconds hand (winged gold guard, blue gem, hilt as counterweight) |
| Three sub-dials in the three nations' colours | **San d'Oria** (red, 9 o'clock): day of week<br>**Bastok** (blue, 3 o'clock): battery E→F<br>**Windurst** (green, 6 o'clock): 24-hour hand |
| Date window | Live date at 4:30 |

Always-on mode switches to an outline-only dial and hides the seconds hand to save power.

## Build & install

You need Android Studio (or the Android SDK plus Gradle 8.7 or newer).

1. Open this `ffxi-watchface/` folder in Android Studio. It will offer to set up the Gradle wrapper.
2. Turn on **Developer options → ADB debugging + Debug over Wi-Fi** on the watch, then pair it:
   `adb pair <ip>:<pair-port>` then `adb connect <ip>:<port>`.
3. Build and install:
   ```
   ./gradlew :app:assembleDebug
   adb install app/build/outputs/apk/debug/app-debug.apk
   ```
4. On the watch, long-press the current face, swipe to the end, tap **+ Add**, and pick
   **Vana'diel Chronograph**. The Pixel Watch app on your phone also lists it.

## Tweaking the look

All art comes from `tools/generate_assets.py` (Pillow and numpy). Edit the colours and
layout constants at the top, then run:

```
python3 tools/generate_assets.py
```

This rewrites the PNGs in `app/src/main/res/drawable-nodpi/` and the previews in `docs/`.
If you move a sub-dial, the date window or a hand size, update the matching
coordinates in `app/src/main/res/raw/watchface.xml`.

Fan-made and unofficial. Not affiliated with Seiko or Square Enix.
