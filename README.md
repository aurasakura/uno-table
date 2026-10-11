# UNO Table

A camera above the table reads the UNO card played into the discard zone, and a projector under the table shows a reaction for it. A rules engine follows the game (turns, card counts, colour) and projects a small HUD at each seat. The face-down draw pile goes in the small lit rectangle next to the discard zone (`DRAW_PILE_*` in `config.py`).

## Install
```
python -m pip install -r requirements.txt
```
On the phone, install **DroidCam**. On the laptop, install the **DroidCam Windows client**, connect them, and check the video shows in the client.

## Run
```
python main.py --probe        # find which camera index is your phone
python main.py --camera 1     # test mode (laptop + phone)
python main.py --projector    # real projector mode
```
All settings are in `config.py`.

## Files
| file | what it does |
|---|---|
| `config.py` | every setting (camera, colours, zone size, projector) |
| `main.py` | app loop, windows, keyboard |
| `game.py` | classic UNO rules for 4 players: turns, direction, colour, card counts, UNO penalty, win (see `rules.md`) |
| `hud.py` | projected HUD: whose turn, card counts facing each seat, direction arrow, current colour |
| `rules.md` | the official rules, how each one changes the game state, and what is not enforced |
| `calibration.py` | click-to-calibrate, `calibration.json` |
| `detector.py` | stillness/change logic, colour classification, `recognise_symbol()` hook for numbers/actions |
| `yolo_symbol.py` | YOLOv8 reads number/skip/reverse/+2/+4 (needs `ultralytics`, model in `models/`; set `YOLO_ENABLED` in `config.py`) |
| `uno_call.py` | UNO call by showing a card back to the camera during the UNO? countdown |
| `reactions.py` | animations: add one with `@reaction("key")` on a class |
| `projector.py` | mirror / rotate / move / resize the projected square |

## Keys
| key | action |
|---|---|
| `c` | calibrate |
| `space` | re-learn the empty discard zone |
| `r y g b w` | fake red / yellow / green / blue / wild |
| `1 2 3 4` | fake skip / +2 / reverse / wild +4 |
| `u` | UNO! (player on 1 card, or the current player before playing) |
| `d` | current player draws a card and passes |
| `z` | undo the last play / draw / UNO call / penalty, e.g. a misread card; then enter the right one with `r y g b w` / `1-4` |
| `v` | win effect (manual) |
| `n` | new game (4 players, 7 cards; empty the discard zone first, the next card on it starts the game) |
| `h` | help · `q`/`Esc` quit |
| arrows / `i j k l` | move square (projector mode) |
| `+` `-` | resize · `o` rotate · `x` mirror · `f` fullscreen · `s` save |

Left-click in the **Debug** window to print a pixel's BGR/HSV values and which colour it counts as.

## Projector mode setup
1. Set `PROJECTOR_WIDTH/HEIGHT` and `PROJECTOR_SCREEN_X` (= your laptop screen width) in `config.py`.
2. Run `python main.py --projector`. Move and resize the square until it fits the table, then press `x`/`o` until the view from above looks right.
3. Press `c`. One white dot is shown at a time. Click it in the Camera window, 4 times, then press Enter.
4. Press `s` to save the placement. You can move or resize the square later without recalibrating.

The table top is 50 x 50 cm with a 4 x 4 cm post at each corner. The square in the projector image covers the whole top, so the posts sit in its corners. The board paints a black square of post + margin (`CORNER_POST_CM` + `CORNER_MARGIN_CM`, 60 px of the 600 px board) at every corner, so no light lands on a post, and the HUD, draw pile and discard zone stay clear of them. Size the square to the full table edge, not to the gap between the posts. The calibration dots sit inside the posts (`CALIB_DOT_INSET`, 7.5 cm in from each corner), so the camera sees each whole dot on the acrylic. If you shrink the square a lot, the dots grow on the board and calibration prints a warning; raise `CALIB_DOT_INSET` then.
