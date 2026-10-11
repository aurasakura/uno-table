"""
Sound effects (see sound_mapping.md). Recipes live in config.SOUND_MAP.

Every recipe is rendered once at startup into a pygame Sound, so a trigger only
starts a channel. Sounds overlap; a new one never cuts off one still playing.
Any audio problem prints one warning and the app carries on silently.

Recipe forms (nest freely):
  "correct.wav"                      a file in config.SOUND_DIR (wav or mp3)
  ("pitch", recipe, semitones)       resample: speed and pitch change together
  ("reverse", recipe)
  ("gain", recipe, g)
  ("trim", recipe)                   cut leading/trailing silence
  ("layer", recipe, recipe, ...)     mix, all starting at t=0
  ("seq", recipe, times, gap_s)      repeat, start-to-start spacing gap_s
  ("chain", gap_s, recipe, ...)      different sounds one after another, start-to-start gap_s
"""
import os

import numpy as np

import config as C
from game import WILDS, card_kind

COLOUR_KEYS = ("red", "yellow", "green", "blue")
STACK_VARIANTS = 8          # pre-rendered pitches for +2 stacks 1..8 (longer stacks reuse the last)
DRUM_DEDUPE_SECONDS = 5.0   # first card after N: no second drum if N drummed this recently

_mixer = None               # pygame.mixer once initialised, else None (silent)
_sounds = {}                # key -> pygame Sound
_files = {}                 # filename -> float32 samples (n, channels)
_rate = 44100
_played = set()             # (key, now) pairs: dedupe within one frame
_frame = None
_warned = False
_last_drum = -1e9
_stack = 0                  # consecutive draw2 cards so far


def _warn(msg):
    global _warned
    if not _warned:
        print(f"[sound] {msg}. Continuing without sound.")
        _warned = True


# ---------------------------------------------------------------------
# Rendering recipes to sample arrays
# ---------------------------------------------------------------------
def _file(name):
    if name not in _files:
        path = os.path.join(C.SOUND_DIR, name)
        snd = _mixer.Sound(path)
        a = _sndarray.array(snd).astype(np.float32) / 32768.0
        _files[name] = a if a.ndim == 2 else a[:, None]
    return _files[name]


def _mix(parts):
    """parts: list of (start_sample, array). Sum them into one array."""
    n = max(s + len(a) for s, a in parts)
    out = np.zeros((n, parts[0][1].shape[1]), np.float32)
    for s, a in parts:
        out[s:s + len(a)] += a
    return out


def _render(r):
    if isinstance(r, str):
        return _file(r)
    op, args = r[0], r[1:]
    if op == "pitch":
        return _pitch_array(_render(args[0]), float(args[1]))
    if op == "reverse":
        return _render(args[0])[::-1].copy()
    if op == "gain":
        return _render(args[0]) * float(args[1])
    if op == "trim":
        a = _render(args[0])
        loud = np.nonzero(np.abs(a).max(1) > 0.02)[0]
        return a[loud[0]:loud[-1] + 1] if len(loud) else a
    if op == "layer":
        return _mix([(0, _render(x)) for x in args])
    if op == "seq":
        a, times, gap = _render(args[0]), int(args[1]), float(args[2])
        return _mix([(int(i * gap * _rate), a) for i in range(times)])
    if op == "chain":
        gap = float(args[0])
        return _mix([(int(i * gap * _rate), _render(x)) for i, x in enumerate(args[1:])])
    raise ValueError(f"unknown sound op {op!r}")


def _to_sound(a):
    peak = float(np.abs(a).max()) if a.size else 0.0
    if peak > 1.0:
        a = a / peak                          # normalise layered/stacked sounds instead of clipping
    pcm = np.ascontiguousarray((a * 32767).astype(np.int16))
    snd = _sndarray.make_sound(pcm)
    snd.set_volume(C.SOUND_VOLUME)
    return snd


def init():
    """Start the mixer and pre-render every recipe. Safe to call when audio is unavailable."""
    global _mixer, _sndarray, _rate
    if not C.SOUND_ENABLED:
        return
    try:
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        import pygame
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.mixer.init()
        pygame.mixer.set_num_channels(32)
        _mixer, _sndarray = pygame.mixer, pygame.sndarray
        _rate = pygame.mixer.get_init()[0]
    except Exception as e:                    # no pygame, no audio device, ...
        _warn(f"audio unavailable ({e})")
        _mixer = None
        return
    for key, recipe in C.SOUND_MAP.items():
        try:
            if key == "draw2_stack":          # pitch rises 2 semitones per stacked +2 (row 11)
                base = _render(recipe)
                for n in range(1, STACK_VARIANTS + 1):
                    _sounds[f"draw2_stack{n}"] = _to_sound(_pitch_array(base, C.SOUND_STACK_STEP * n))
            else:
                _sounds[key] = _to_sound(_render(recipe))
        except Exception as e:
            print(f"[sound] could not build {key!r} from {recipe!r}: {e}")
    print(f"[sound] {len(_sounds)} sounds ready")


def _pitch_array(a, semitones):
    ratio = 2 ** (semitones / 12)
    n = max(1, int(len(a) / ratio))
    src, idx = np.arange(n) * ratio, np.arange(len(a))
    return np.stack([np.interp(src, idx, a[:, c]) for c in range(a.shape[1])], 1).astype(np.float32)


def length(key):
    """Seconds, or None if the key has no sound."""
    s = _sounds.get(key)
    return s.get_length() if s else None


# ---------------------------------------------------------------------
# Playing
# ---------------------------------------------------------------------
def play(key, now=None):
    """Start `key` on a free channel. The same key twice in one frame (same `now`) plays once."""
    global _frame, _last_drum
    if _mixer is None or key not in _sounds:
        return False
    if now is not None:
        if now != _frame:
            _frame = now
            _played.clear()
        if key in _played:
            return False
        _played.add(key)
    if key == "start" and now is not None:
        _last_drum = now
    try:
        ch = _mixer.find_channel(True)        # True: steal the oldest channel only if all 32 are busy
        if ch is not None:
            ch.play(_sounds[key])
        return True
    except Exception as e:
        _warn(f"playback failed ({e})")
        return False


def card_key(card, prev_top, colour_unknown):
    """Rows 3-11 of sound_mapping.md: the one sound for a played card, by priority
    wild4 > draw2 (stacked or not) > skip > reverse > wild > colour change > plain number."""
    global _stack
    kind = card_kind(card)
    if kind == "draw2":
        _stack += 1
        return "draw2" if _stack == 1 else f"draw2_stack{min(_stack - 1, STACK_VARIANTS)}"
    _stack = 0
    if kind in ("wild4", "skip", "reverse", "wild"):
        return kind
    if card.colour not in COLOUR_KEYS:
        return None
    prev_kind = card_kind(prev_top) if prev_top is not None else None
    if (not colour_unknown and kind is not None and prev_kind == kind
            and prev_top.colour != card.colour):
        return f"change_{card.colour}"        # row 4: same number, new colour
    return card.colour                        # row 3 (and row 9: first colour after a wild)


def on_card(card, prev_top, colour_unknown, events, now):
    """Sound for one card landing on the pile, given the game events it produced.
    Event sounds (UNO, penalty, win) are played separately by on_event."""
    kinds = {e.kind for e in events}
    if "reject" in kinds:
        play("illegal", now)                  # row 14
        return
    if prev_top is None:                      # first card of the game (row 1)
        if now is None or now - _last_drum > DRUM_DEDUPE_SECONDS:
            play("start", now)
        else:
            play(card_key(card, prev_top, colour_unknown), now)
        return
    if "play" not in kinds:                   # game already over: nothing was played
        return
    key = card_key(card, prev_top, colour_unknown)   # also keeps the +2 stack count in step
    if "warn" in kinds:
        play("illegal", now)                  # row 14 replaces the card sound
        return
    play(key, now)
    if "win" not in kinds:
        play("turn", now)                     # row 12: additive, every valid card


EVENT_KEYS = {"penalty": "forgot_uno", "uno": "uno", "uno_due": "uno_due", "win": "win"}


def on_event(event, now):
    """Game events that have their own sound. 'draw' from +2/+4 is covered by the card sound."""
    key = EVENT_KEYS.get(event.kind)
    if key:
        play(key, now)


def reset():
    """New game: forget the +2 stack."""
    global _stack
    _stack = 0
