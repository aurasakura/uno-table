# Shortened sound effects

Built from the originals in `sound_effects/`, which are left untouched. Output: 44.1 kHz, 16-bit PCM WAV, same channel count as the source. Trim points come from RMS per 100 ms (20-50 ms near cuts), not guesses. `alimiter` stops the 32k/24k to 44.1k resample from clipping. It only touches peaks above -0.26 dBFS.

| File | Original | New | Method |
|---|---|---|---|
| card_flick | 4.20 s | 0.45 s | (c) trim: onset at 0.06 s, keep the loudest 0.45 s of the riffle, 0.15 s fade |
| drum | 4.87 s | 1.50 s | (c) trim: the roll is one 1.0 s bar played twice; keep bar 2 (1.00-2.05 s), which ends naturally, plus 0.45 s of its tail, faded |
| sad_trombone | 5.26 s | 1.99 s | (d) trim 0.22-4.62 s (leading silence, dead tail) + atempo 2.2x |
| cheer | 4.44 s | 2.80 s | (c) trim first 2.8 s (crowd is steady 0-2.1 s), 0.6 s fade |
| explosion | 2.82 s | 1.50 s | (c) trim: skip the 0.4 s rumble before the boom (boom at 0.48 s), 0.6 s fade |

Why these picks:
- **sad_trombone**: a pitch track of the four notes gives 238, 227, 212, 200 Hz in the original. atempo keeps all four exactly. `rubberband` dropped a frame and jumped an octave on note 3. asetrate (chipmunk) moves the notes up to 525-441 Hz (+13.7 semitones), so it no longer sounds like a trombone. Trimming alone would lose the descent.
- **card_flick, drum, cheer, explosion**: trimming keeps the original quality and timing. atempo at 3-8x smears the flick transients and drum hits, and chipmunk makes them squeak. A crowd cheer and an explosion have no melody to keep, so cutting the tail loses nothing.
- **tick.mp3** (3.79 s) is not re-encoded. Its content is 0.06 s, and SOUND_MAP already wraps it in `("trim", ...)`.
- **alarm.wav** (1.57 s, 1.38 s of content) is not re-encoded. See the optional note below.

## Exact commands

Run from `sound_effects/`, with `L="alimiter=limit=0.97:level=disabled:latency=1"`.

```
ffmpeg -i card_flick.mp3 -af "atrim=start=0.05:end=0.50,asetpts=PTS-STARTPTS,afade=t=in:d=0.005,afade=t=out:st=0.30:d=0.15,aresample=44100" -c:a pcm_s16le short/card_flick.wav
ffmpeg -i drum.mp3 -af "atrim=start=1.00:end=2.50,asetpts=PTS-STARTPTS,afade=t=in:d=0.005,afade=t=out:st=1.05:d=0.45,aresample=44100,$L" -c:a pcm_s16le short/drum.wav
ffmpeg -i sad_trombone.wav -af "atrim=start=0.22:end=4.62,asetpts=PTS-STARTPTS,afade=t=out:st=4.08:d=0.32,atempo=2.2,aresample=44100" -c:a pcm_s16le short/sad_trombone.wav
ffmpeg -i cheer.wav -af "atrim=start=0:end=2.80,asetpts=PTS-STARTPTS,afade=t=out:st=2.20:d=0.60,aresample=44100,$L" -c:a pcm_s16le short/cheer.wav
ffmpeg -i explosion.wav -af "atrim=start=0.40:end=1.90,asetpts=PTS-STARTPTS,afade=t=in:d=0.005,afade=t=out:st=0.90:d=0.60,aresample=44100,$L" -c:a pcm_s16le short/explosion.wav
```

## Recommended SOUND_MAP changes (config.py, not applied)

`sound._file` joins `SOUND_DIR` with the name, so `"short/<name>.wav"` loads as is. Each file was checked with `sound._render` and `sound._to_sound`.

```
-    "start":   "drum.mp3",
+    "start":   "short/drum.wav",
-    "wild4":   "explosion.wav",
+    "wild4":   "short/explosion.wav",
-    "draw":    "card_flick.mp3",
+    "draw":    "short/card_flick.wav",
-    "forgot_uno": "sad_trombone.wav",
+    "forgot_uno": "short/sad_trombone.wav",
-    "win":     "cheer.wav",
+    "win":     "short/cheer.wav",
```

Keep the trailing comments on each line.

Optional: `alarm.wav` already holds three beeps, 0.48 s apart. `("seq", "alarm.wav", 3, 0.35)` layers three copies into about 2.3 s of overlapping beeps. If that overlap was not intended, `"uno": ("trim", "alarm.wav"),` gives three clean beeps in 1.4 s.
