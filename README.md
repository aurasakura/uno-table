# UNO Table

A camera above the table reads the UNO card played into the discard zone, and a projector under the table shows a reaction for it.

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
| `calibration.py` | click-to-calibrate, `calibration.json` |
| `detector.py` | stillness/change logic, colour classification, `recognise_symbol()` hook for numbers/actions |
| `yolo_symbol.py` | YOLOv8 reads number/skip/reverse/+2/+4 (needs `ultralytics`, model in `models/`; set `YOLO_ENABLED` in `config.py`) |
| `reactions.py` | animations: add one with `@reaction("key")` on a class |
| `projector.py` | mirror / rotate / move / resize the projected square |

## Keys
| key | action |
|---|---|
| `c` | calibrate |
| `space` | re-learn the empty discard zone |
| `r y g b w` | fake red / yellow / green / blue / wild |
| `1 2 3 4` | fake skip / +2 / reverse / wild +4 |
| `h` | help · `q`/`Esc` quit |
| arrows / `i j k l` | move square (projector mode) |
| `+` `-` | resize · `o` rotate · `x` mirror · `f` fullscreen · `s` save |

Left-click in the **Debug** window to print a pixel's BGR/HSV values and which colour it counts as.

## Projector mode setup
1. Set `PROJECTOR_WIDTH/HEIGHT` and `PROJECTOR_SCREEN_X` (= your laptop screen width) in `config.py`.
2. Run `python main.py --projector`. Move and resize the square until it fits the table, then press `x`/`o` until the view from above looks right.
3. Press `c`. One white dot is shown at a time. Click it in the Camera window, 4 times, then press Enter.
4. Press `s` to save the placement. You can move or resize the square later without recalibrating.
