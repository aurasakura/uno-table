# Connected UNO projector tester

This copy of the supplied projector tester receives live card detections from the current UNO app. Original effects, themes, placement controls, and embedded sounds are retained. The original Downloads file is unchanged.

## Use now

1. Keep DroidCam connected. Close the separate Python UNO camera app if it is using the same camera.
2. Open http://127.0.0.1:8765/projector in a separate browser window on the projector display. Click to start audio, finish placement/mirroring/rotation, press F for fullscreen, and H to hide the help panel.
3. Open http://127.0.0.1:8765/controls on the laptop. Confirm the preview actually shows the phone/table. Camera index 2 is configured; the bridge has verified 1280x720 frames, but camera identity must be visually confirmed by the operator.
4. Click **Calibrate projected dots**. In the camera preview, click the centre of the projected dot. Wait for it to move, then click the next one, four in total. Click the projected dots, not the tabletop corners. This maps browser mirroring and rotation directly to the camera.
5. Empty the central discard zone. Click **Start detection**, leave the centre empty and still until status says **learned empty zone**, then place a card and clear your hands.
6. The last-card display shows the exact detected colour and number/action. Only accepted joint detections trigger effects. Unknown/conflicting readings wait. Moving/resizing/rotating/mirroring the projector page, changing fullscreen, or enabling a test pattern requires recalibration. Keep one projector page open.

The HTML is an effects tester with a simple turn sequence, not the full Python game engine. Camera-triggered effects use the recognised colour; manual keys still work. The automatic tour is disabled while recognition is armed. The central zone stays plain; screen shake is suppressed while detection is armed so it cannot move the camera's target.

## Run and stop

The bridge binds to all interfaces at port 8765 so a phone on the same Wi-Fi can use the remote. Use it on a trusted network; the remote has no login. It uses the existing project Python environment and models, with MSMF camera capture. Nothing is uploaded. Camera JPEG previews remain in memory and are accessible on the LAN; camera recordings are not saved.

To run it again from this folder:

```powershell
.\start.ps1
```

Camera/port overrides: `.\start.ps1 -Camera 2 -Port 8765`. Leave that terminal open; Ctrl+C stops a foreground run. The initial background run has `server.pid`, `server.log`, and `server-errors.log` in this folder. Stop that run with:

```powershell
.\stop.ps1
```

Source application: `C:\Users\Woo\.t3\projects\uno-table`. This bridge imports its `CardDetector`, `open_camera`, configuration, and installed `models/symbols.pt`; it does not retrain or replace weights. No global service or package was installed. Calibration is session-only and separate from the Python app's saved calibration.

## Verification and remaining limits

- 19 backend checks: HTTP endpoints, calibration, invalid points, pause/invalidation, duplicate-read prevention, and a yellow 0 passing through the real model and bridge on a synthetic board.
- 14 headless browser checks: live 1280x720 camera preview, required calibration, exact colour/number effect mapping using simulated messages, event deduplication, no replay on reconnect, tour guard, and calibration-dot location. No JavaScript runtime errors.
- Original embedded sound data is unchanged. Audio playback through physical speakers and physical projection alignment were not tested.
- Actual table calibration and card-to-projector operation still need the physical steps above. The classifier's previously measured errors/abstentions remain; this connection does not improve model accuracy.

Machine-readable check results: `verification.json` and `browser-verification.json`.

## Demo fallback and phone remote

Changes on disk do not update an already running Python backend. Leave the current camera-owning server alone. These endpoints become available on port 8765 after the operator later starts the updated server. The port 8766 check below never opens a camera.

1. Open `/projector` and click **Click to start** on that page once to enable effects and audio. Leave it open before sending cards; events from before startup or reconnect are deliberately not replayed.
2. In `/controls`, select **Manual (remote only)** when recognition fails. Manual pauses recognition and blocks camera events. **Auto (camera)** rejects remote input. **Both** accepts remote and camera events. Changing back to Auto or Both does not automatically arm the camera: calibrate and click **Start detection** as needed. Both is the normal camera-enabled startup default; `--no-camera` starts in Manual.
3. The controls page and server terminal show LAN URLs such as `http://172.20.10.2:8765/remote`. Choose the laptop's Wi-Fi address, not a VPN or virtual adapter address. The address may change. Connect the phone to the same Wi-Fi, open `/remote`, choose one of four colours, then tap 0-9, Skip, Reverse, +2, Wild, +4, UNO, Draw or Win. Wild and +4 use the wild colour. Buttons confirm the accepted event ID; they do not confirm projector playback. Keep one projector page open.
4. Windows Firewall may prompt for Python. Allow **Private networks** if appropriate for this Wi-Fi. No firewall setting is changed by the bridge. If the phone cannot connect, check the laptop Wi-Fi IP, firewall permission and Wi-Fi client isolation. Physical phone connectivity still needs an operator check.

Each accepted injection uses the same event counter, recent-event queue and last-card update as accepted camera detections. Projectors consume each ID once. Intentional repeated taps create separate events, even for identical cards. Manual injection uses the existing effects and sound recipes, including UNO, Draw and Win. This remains an effects demo, not a UNO rules engine.

```powershell
Invoke-RestMethod 'http://127.0.0.1:8765/api/inject' -Method Post -ContentType 'application/json' -Body '{"colour":"red","symbol":"7"}'
Invoke-RestMethod 'http://127.0.0.1:8765/api/inject?c=red&s=7'
```

`POST /api/mode {"mode":"manual"}` changes input mode; values are `auto`, `manual`, `both`. `/api/state` includes `mode` and `remote_urls`. The GET injection endpoint changes state for easy demo testing. Avoid prefetching its links. Invalid input returns 400 without adding an event. Actions accept `draw2` / `+2` / `plus2` and `wild4` / `+4` / `plus4`.

Camera-free check from this folder:

```powershell
& 'C:\Users\Woo\.t3\projects\culture-makeathon-common-ground\detector\.venv\Scripts\python.exe' -B -u server.py --port 8766 --no-camera
# In a second terminal:
node verify-fallback.cjs
```

The check launches a separate headless Edge profile in this folder and writes `fallback-verification.json`. It covers API validation, modes, historical-event suppression, actual API-to-projector effects, duplicate-ID suppression, decoded sound paths, LAN URL display and phone button requests. It does not test physical projection, speaker output, actual phone Wi-Fi or camera recognition. The server on 8765 is not stopped, restarted or accessed for writes.
