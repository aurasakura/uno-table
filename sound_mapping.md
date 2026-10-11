# Sound mappings

Spec for wiring audio into the UNO table app. Durations are ignored: play every file as-is. Only sounds that can be produced from the files in `sound_effects/` plus code-side operations are listed.

## Source files

All paths are relative to the repo root. Load each file once at startup into memory (decoded samples) so triggers have no disk latency.

| id | file |
|---|---|
| `alarm` | `sound_effects/alarm.wav` |
| `bonk` | `sound_effects/bonk.mp3` |
| `buzzer` | `sound_effects/buzzer.wav` |
| `card_flick` | `sound_effects/card_flick.mp3` |
| `cheer` | `sound_effects/cheer.wav` |
| `correct` | `sound_effects/correct.wav` |
| `drum` | `sound_effects/drum.mp3` |
| `explosion` | `sound_effects/explosion.wav` |
| `sad_trombone` | `sound_effects/sad_trombone.wav` |
| `swish` | `sound_effects/swish.mp3` |
| `thud` | `sound_effects/thud.wav` |
| `tick` | `sound_effects/tick.mp3` |

## Code-side operations

Implement these as small helpers in a new module (suggested: `sounds.py`). Work on numpy sample arrays so they compose.

| op | meaning |
|---|---|
| `pitch(sound, semitones)` | resample by `2 ** (semitones / 12)` (speed and pitch change together; length changes, which is fine) |
| `reverse(sound)` | reverse the sample array |
| `layer(a, b, ...)` | mix sounds from t=0, sum samples, clip or normalise to avoid overflow |
| `seq(sound, times, gap_s)` | play the same sound `times` times, start-to-start spacing `gap_s` |
| `gain(sound, g)` | multiply amplitude |

Playback: any mixer that supports overlapping channels (for example `pygame.mixer`). A new trigger must not cut off sounds that are still playing.

## Pitch table for colour chimes

Base file `correct` is assumed to sit at C. If it does not, shift all offsets by the difference.

| colour | note | semitones from C |
|---|---|---|
| red | C | 0 |
| blue | G | +7 |
| green | A | +9 |
| yellow | E | +4 |

## Mappings

| # | Action | Trigger | Sound recipe |
|---|---|---|---|
| 1 | Game start | Button / first card | `drum` |
| 2 | Deal | Button | `seq(card_flick, times=N, gap_s=0.1)`, N = number of cards dealt; or a single `card_flick` |
| 3 | Number card (red/blue/green/yellow) | Camera read, colour known | `pitch(correct, CHIME[colour])` using the table above |
| 4 | Same number, new colour | Camera read, same number as previous card but different colour | `layer(pitch(correct, CHIME[new_colour]), swish)` |
| 5 | Skip | Camera read, symbol `skip` | `layer(bonk, buzzer)` |
| 6 | Reverse | Camera read, symbol `reverse` | `reverse(swish)` |
| 7 | +2 | Camera read, symbol `draw2` | `seq(thud, times=2, gap_s=0.25)` |
| 8 | Wild | Camera read, colour `wild` | `seq` of `pitch(correct, s)` for s in `[0, 4, 7, 9]` (C, E, G, A), gap 0.1 s, then final note +12 |
| 9 | Wild colour chosen | Next card read after a wild, or button | `pitch(correct, CHIME[chosen_colour])` |
| 10 | Wild +4 | Camera read, symbol `wild4` | `explosion` |
| 11 | Stacking +2 on +2 | Camera read, `draw2` while previous card was `draw2` | `pitch(thud, 2 * stack_count)`, where `stack_count` = number of consecutive `draw2` cards (1 for the first stack). Reset when any other card is played |
| 12 | Turn passes | After any valid card | `tick`, `gain 0.5`. Play after the card's own sound has started, not instead of it |
| 13 | Draw a card | Button / timeout | `card_flick` |
| 14 | Invalid play | Camera read that breaks the rules | `pitch(buzzer, -5)` |
| 15 | UNO! | Button | `seq(alarm, times=3, gap_s=0.35)` |
| 16 | Forgot UNO | Button | `sad_trombone` |
| 17 | Win | Last card / button | `cheer` |

Rules:
- Rows 3 to 11 are mutually exclusive per camera read. Choose by priority: `wild4` > `draw2` (stacked or not) > `skip` > `reverse` > `wild` > colour-change (row 4) > plain number (row 3).
- Row 12 is additive: it plays with the sound above, for every valid card.
- Row 8 and row 9 share the `correct` file. Both can overlap safely.

## Dependencies on game logic that does not exist yet

The current code (`detector.py`, `reactions.py`) emits a `Card(colour, symbol)` and nothing else. The following must be added before the table can be wired fully:

| needed | used by rows | note |
|---|---|---|
| Symbol recognition (`recognise_symbol()` returns `None` today) | 4 to 7, 10, 11 | until implemented, only the colour chimes (3) and wild (8) can fire from the camera. Fake keys `1`-`4` in `main.py` already emit `skip`, `draw2`, `reverse`, `wild4` for testing |
| Number tracking (previous card colour and symbol) | 4 | store on the game state, compare on each read |
| `stack_count` | 11 | increment on consecutive `draw2`, reset otherwise |
| Rule check for valid or invalid play | 12, 14 | needs previous card and current card |
| Buttons or keys for game start, deal, draw, UNO!, forgot UNO, win, wild colour chosen | 1, 2, 9, 13, 15, 16, 17 | suggest new keys in `handle_key` in `main.py`, with a help line in `HELP` |

## Suggested integration points

- `Stage.trigger(card, now)` in `reactions.py` is already called for both detected and faked cards. Call a new `sounds.play_for_card(card, game_state)` from there so sound and animation stay in step.
- Add a `sounds.py` module with: `load_all()`, the ops above, a `play(sound)` function, and `play_for_card()` implementing the priority rule.
- Add `SOUND_ENABLED` and `SOUND_VOLUME` to `config.py`, and add a pygame (or chosen mixer) line to `requirements.txt`.

## Not covered (needs new audio, not code)

Power-up sweep, true tape-rewind, sparkle run, rumble lead-in, fanfare, idle/attract loop, background loop (including colour-following mood and music ducking). These have no source file and cannot be synthesised acceptably from the existing files, so they are excluded.
