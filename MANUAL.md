# UNO Table: teammate & demo manual

## 1. Setup in 5 minutes

1. Power laptop, phone and projector. Secure the phone above the whole table; project from underneath. Extend the desktop to the projector.
2. Connect phone DroidCam to the **DroidCam Windows client**; confirm live video.
3. Open PowerShell in the team repo and run:
   ```powershell
   cd C:\Users\Woo\.t3\projects\uno-table
   python -m pip install -r requirements.txt  # first setup only
   python main.py --probe
   python main.py --projector --camera 1
   ```
   Replace `1` with the phone index. Laptop-only practice: `python main.py --test --camera 1`.
4. Click an app window. Fit the square to the **whole 50 × 50 cm table edge**, including corners, using the placement keys below.
5. Empty **both draw pile spot and discard zone**. Press `C`; click each white dot in **Camera** (four total), then Enter. In test mode, click paper corners: top-left, top-right, bottom-right, bottom-left. Leave the zone empty for a second. Press `S` to save placement.

## 2. How to play

- Seat P1–P4; deal **7 each**. Put the face-down deck in the lit draw rectangle above-right of centre. Turn one card face up into the centre to start.
- Follow the turn indicator. Match colour, number or symbol, or play Wild. Put cards **in the centre zone one at a time and let go**. Clear your hands; wait for the reaction.
- Voluntary draw: take one; operator presses `D`, passing your turn. Keep it until next turn. Pick up automatic +2/+4/UNO penalties without pressing `D`.
- When **UNO?** flashes, hold a card **back up to the camera**, within the table view, for **0.4 seconds**. Call within **4 seconds**, before the next player acts; `U` is the operator fallback. Missing UNO adds two cards.
- The table counts cards and turns; play in order. Winner at **0**. After Wild, the next card sets the tracked colour. No stacking or +4 challenge enforcement; illegal plays warn but count.

## 3. Operator keys

On the **laptop running `main.py`**, click an app window first. Either letter case works.

| Key | Action |
|---|---|
| `C` / Space | Calibrate / relearn **empty** discard zone |
| `R Y G B W` | Enter red / yellow / green / blue / Wild |
| `1 2 3 4` | Enter Skip / +2 / Reverse / Wild +4 |
| `U` / `D` | Call UNO / current player draws one and passes |
| `Z` / `N` | Undo last action / new game (4 players, 7 each) |
| `V` | Manual win effect; does not declare a game winner |
| `H` / `Q` or Esc | Print help / quit |
| Arrows or `I J K L` | Move square: `I` up, `J` left, `K` down, `L` right* |
| `+ -` / `O` / `X` | Resize / rotate 90° / toggle mirror* |
| `F` / `S` | Toggle fullscreen / save placement* |

*Projector mode only. Debug left-click prints colour values. Manual entries are plays: colour keys cannot specify numbers; `1–3` inherit the previous colour (otherwise random). Colour then action records **two plays**.*

## 4. When something goes wrong

| Problem | What to do |
|---|---|
| Misread card | Stop play. `Z`, then replacement via `R Y G B W` or `1–4` (limits above). Check turn/counts. |
| Debug says colour/symbol unknown or conflicting | No camera play counted. Reposition card, clear hands, improve lighting, or use an explicit manual override. Dark cards are not assumed Wild. |
| Camera disconnected | Reconnect DroidCam. Game/UNO timer continue without detection. If video stays absent, quit, probe, relaunch; restart resets game. |
| Projection misaligned | Adjust placement, then `S`; empty zone while it relearns. Camera moved/resolution changed: `C` again. |
| Corner shadows | Black corner blocks protect posts. Fit full table edge; keep dots clear of posts. |
| Sound silent | Check volume/output (including HDMI) and console warnings. Ask teammate about missing `pygame-ce`, audio device or assets. Silent play works. |
| New game | Empty discard zone **before `N`**; wait a second, deal 7 each, place starting card. |

## 5. Before the demo checklist

Automatic plays need both colour and number/action recognition. Wild/+4 need a confident symbol and multiple hues, never darkness alone. The current supplied-deck classifier still misses/confuses6,9,+4; validate real cards before relying on it. `python main.py --collect LABEL` saves localized stable crops even when the symbol is unknown, without counting unknowns as plays. Empty the zone before calibration; retain steady lighting and use Space to relearn an empty zone if it changes.

- [ ] Laptop, phone and projector powered; cables secure.
- [ ] DroidCam video live; correct camera index selected.
- [ ] Projector mode running on the second screen.
- [ ] Full table aligned; orientation correct; placement saved.
- [ ] Empty-zone calibration complete; dots clear of posts.
- [ ] One real card read correctly; sound checked.
- [ ] UNO card-back call tested; operator knows `U`, `Z` and `D`.
- [ ] Test cards cleared; `N` pressed on an empty zone; 7 cards dealt each.
