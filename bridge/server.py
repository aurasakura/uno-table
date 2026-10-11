"""Local camera bridge for the existing HTML projector tester. No GUI or recording."""
import argparse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
import socket
from pathlib import Path
import sys
import threading
import time
from urllib.parse import urlsplit, parse_qs
import uuid

HERE = Path(__file__).resolve().parent
APP = Path(r"C:\Users\Woo\.t3\projects\uno-table")
sys.path.insert(0, str(APP))
import cv2
import numpy as np
import calibration
import config as C
from detector import CardDetector
from main import open_camera
import yolo_symbol

# Resolve model paths without depending on the launcher's working directory.
C.SYMBOL_MODEL = str(APP / C.SYMBOL_MODEL)
C.YOLO_MODEL = str(APP / C.YOLO_MODEL)
def lan_addresses():
    return sorted({item[4][0] for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
                   if not item[4][0].startswith('127.')})


DOTS = np.float32([[90, 90], [510, 90], [510, 510], [90, 510]])


class Bridge:
    def __init__(self, camera_index=2):
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.session = uuid.uuid4().hex
        self.camera = dict(connected=False, index=camera_index, width=0, height=0, error=None)
        self.cal = dict(valid=False, step=None, points=[])
        self.armed = False
        self.mode = 'both'
        self.remote_urls = []
        self.status = "Waiting for camera; then calibrate the projected dots"
        self.H = None
        self.jpeg = None
        self.detector = CardDetector()
        self.last_card = None
        self.event_id = 0
        self.events = deque(maxlen=64)
        self.model = "symbol classifier" if Path(C.SYMBOL_MODEL).exists() else "pretrained detector fallback"

    def snapshot(self):
        with self.lock:
            return dict(session=self.session, camera=dict(self.camera),
                        calibration=dict(self.cal, points=list(self.cal['points'])),
                        armed=self.armed, mode=self.mode, remote_urls=self.remote_urls, status=self.status, last_card=self.last_card,
                        event_id=self.event_id, events=list(self.events), model=self.model,
                        still_seconds=C.STILL_SECONDS)

    def accept_card(self, colour, symbol, source='camera'):
        # Both sources share the monotonic ID consumed once by each projector.
        with self.lock:
            self.event_id += 1
            event = dict(id=self.event_id, colour=colour, symbol=symbol,
                         time=time.time(), source=source)
            self.last_card = dict(colour=colour, symbol=symbol)
            self.events.append(event)
            print('CARD ' + json.dumps(event), flush=True)
            return self.snapshot()

    def inject(self, payload):
        colour, symbol = payload.get('colour'), payload.get('symbol')
        if not isinstance(colour, str) or not isinstance(symbol, (str, int)) or isinstance(symbol, bool):
            raise ValueError('Provide colour and symbol')
        colour, symbol = colour.lower(), str(symbol).lower()
        symbol = {'+2': 'draw2', 'plus2': 'draw2', '+4': 'wild4', 'plus4': 'wild4'}.get(symbol, symbol)
        regular = {'red', 'blue', 'green', 'yellow'}
        if symbol in {'wild', 'wild4'}:
            colour = 'wild'
        elif colour not in regular or symbol not in set('0123456789') | {'skip', 'reverse', 'draw2', 'uno', 'draw', 'win'}:
            raise ValueError('Invalid colour or symbol')
        with self.lock:
            if self.mode == 'auto':
                raise ValueError('Remote input is disabled in Auto mode; select Manual or Both')
            return self.accept_card(colour, symbol, 'remote')

    def pause(self, message):
        self.armed = False
        self.detector.reset()
        self.status = message

    def command(self, path, payload):
        with self.lock:
            if path == '/api/inject':
                return self.inject(payload)
            elif path == '/api/mode':
                mode = payload.get('mode')
                if mode not in ('auto', 'manual', 'both'):
                    raise ValueError('Mode must be auto, manual or both')
                self.mode = mode
                if mode == 'manual':
                    self.pause('Manual mode: use the phone remote')
                else:
                    self.status = 'Camera input enabled; calibrate and Start detection if paused'
            elif path == '/api/pause':
                self.pause('Paused')
            elif path == '/api/calibration/invalidate':
                self.pause('Projection changed: calibrate again')
                self.cal = dict(valid=False, step=None, points=[])
                self.H = None
            elif path == '/api/calibration/start':
                if not self.camera['connected']:
                    raise ValueError('Camera is not connected')
                self.pause('Click the projected dot in the camera preview')
                self.cal = dict(valid=False, step=0, points=[])
                self.H = None
            elif path == '/api/calibration/point':
                if self.cal['step'] is None or not self.camera['connected']:
                    raise ValueError('Start calibration with a connected camera first')
                x, y = payload.get('x'), payload.get('y')
                if (type(x) not in (int, float) or type(y) not in (int, float)
                        or not math.isfinite(x) or not math.isfinite(y)
                        or not 0 <= x < self.camera['width'] or not 0 <= y < self.camera['height']):
                    raise ValueError('Point must be inside the camera image')
                points = self.cal['points'] + [[x, y]]
                if len(points) == 4:
                    problem = calibration.quad_problem(points)
                    if problem:
                        self.cal = dict(valid=False, step=0, points=[])
                        raise ValueError(problem + '; click the four dots again')
                    self.H = cv2.getPerspectiveTransform(np.float32(points), DOTS)
                    self.cal = dict(valid=True, step=None, points=points)
                    self.status = 'Calibrated. Empty the discard zone, then Start recognition'
                else:
                    self.cal['points'] = points
                    self.cal['step'] = len(points)
            elif path == '/api/arm':
                if self.mode == 'manual':
                    raise ValueError('Select Auto or Both before starting camera detection')
                if not self.camera['connected'] or not self.cal['valid'] or self.H is None:
                    raise ValueError('Connect the camera and calibrate all four dots first')
                self.detector.reset()
                self.armed = True
                self.status = 'Learning empty discard zone: keep it empty and still for a second'
            else:
                raise KeyError(path)
            return self.snapshot()

    def process_frame(self, frame, now):
        """Actual camera path, also exercised with synthetic boards in headless checks."""
        with self.lock:
            height, width = frame.shape[:2]
            sample = frame[::16, ::16].astype(np.float32)
            mean = sample.mean(axis=(0, 1))
            if (sample.std(axis=(0, 1)).max() < 1 and mean[1] > 30
                    and mean[1] > 2 * max(mean[0], mean[2], 1)):
                # DroidCam's documented green-screen failure returns valid-sized
                # buffers without a camera picture; never treat them as ready.
                message = 'DroidCam is sending a solid green frame. Use File > Exit in DroidCam, then reopen it.'
                self.camera.update(connected=False, width=width, height=height, error=message)
                ok, encoded = cv2.imencode('.jpg', frame)
                self.jpeg = encoded.tobytes() if ok else None
                self.pause(message)
                self.cal = dict(valid=False, step=None, points=[])
                self.H = None
                return
            was_connected = self.camera['connected']
            if self.cal['valid'] and (width != self.camera['width'] or height != self.camera['height']):
                self.pause('Camera resolution changed: calibrate again')
                self.cal = dict(valid=False, step=None, points=[])
                self.H = None
            self.camera.update(connected=True, width=width, height=height, error=None)
            if not was_connected:
                self.status = 'Camera ready. Calibrate the projected dots before starting detection'
            # JPEG remains in memory; LAN users can also view the preview.
            ok, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if ok:
                self.jpeg = encoded.tobytes()
            if self.mode == 'manual' or not self.armed or self.H is None:
                return
            board = cv2.warpPerspective(frame, self.H, (C.BOARD_PX, C.BOARD_PX))
            card = self.detector.update(board, now)
            self.status = self.detector.status
            if card is not None:
                self.accept_card(card.colour, card.symbol)

    def camera_loop(self):
        cap = None
        try:
            while not self.stop.is_set():
                if cap is None:
                    cap = open_camera(self.camera['index'])
                ok, frame = cap.read() if cap.isOpened() else (False, None)
                if not ok:
                    with self.lock:
                        self.camera.update(connected=False, error='No frames. Check DroidCam; close other camera apps.')
                        self.jpeg = None
                        self.pause('Camera disconnected; reconnect, calibrate and start again')
                        self.cal = dict(valid=False, step=None, points=[])
                        self.H = None
                    cap.release()
                    cap = None
                    self.stop.wait(2)
                    continue
                try:
                    self.process_frame(frame, time.monotonic())
                except Exception as exc:
                    with self.lock:
                        self.pause('Recognition error: ' + str(exc))
                    print('ERROR ' + repr(exc), flush=True)
                self.stop.wait(0.03)
        finally:
            if cap is not None:
                cap.release()


def make_handler(bridge):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            if args and str(args[1]) not in ('200', '204'):
                super().log_message(fmt, *args)

        def allowed_host(self):
            return self.headers.get('Host') in {f'{host}:{self.server.server_port}' for host in ['127.0.0.1', 'localhost', *self.server.lan_hosts]}

        def send(self, status, body, mime='application/json'):
            if isinstance(body, dict):
                body = json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            if not self.allowed_host():
                self.send(403, {'error': 'Use the laptop IP or localhost'})
                return
            path = urlsplit(self.path).path
            if path == '/api/inject':
                origin = self.headers.get('Origin')
                if (origin and origin != 'http://' + self.headers.get('Host', '')) or self.headers.get('Sec-Fetch-Site') == 'cross-site':
                    self.send(403, {'error': 'Same-origin requests only'})
                    return
                query = parse_qs(urlsplit(self.path).query)
                try:
                    self.send(200, bridge.inject({'colour': query.get('c', [None])[0], 'symbol': query.get('s', [None])[0]}))
                except (ValueError, TypeError) as exc:
                    self.send(400, {'error': str(exc)})
            elif path == '/api/state':
                self.send(200, bridge.snapshot())
            elif path == '/api/frame.jpg':
                with bridge.lock:
                    jpeg = bridge.jpeg
                self.send(200, jpeg, 'image/jpeg') if jpeg else self.send(503, {'error': 'Waiting for camera frames'})
            elif path in ('/', '/projector', '/projector.html', '/controls', '/control.html', '/remote'):
                filename = 'remote.html' if path == '/remote' else ('control.html' if path in ('/controls', '/control.html') else 'projector.html')
                file = HERE / filename
                self.send(200, file.read_bytes(), 'text/html; charset=utf-8') if file.exists() else self.send(503, {'error': 'Page not ready'})
            else:
                self.send(404, {'error': 'Not found'})

        def do_POST(self):
            origin = self.headers.get('Origin')
            if not self.allowed_host() or (origin and origin != 'http://' + self.headers.get('Host', '')):
                self.send(403, {'error': 'Same-origin local requests only'})
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 <= size <= 4096 or not self.headers.get('Content-Type', '').startswith('application/json'):
                    raise ValueError('Expected a small JSON object')
                payload = json.loads(self.rfile.read(size) or b'{}')
                if not isinstance(payload, dict):
                    raise ValueError('Expected JSON object')
                result = bridge.command(urlsplit(self.path).path, payload)
                self.send(200, result)
            except (ValueError, TypeError) as exc:
                self.send(400, {'error': str(exc)})
            except KeyError:
                self.send(404, {'error': 'Unknown command'})
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--camera', type=int, default=2)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--host', default='0.0.0.0', help='HTTP listen address')
    parser.add_argument('--no-camera', action='store_true', help='API/browser checks only; no camera access')
    args = parser.parse_args()
    bridge = Bridge(args.camera)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(bridge))
    server.lan_hosts = lan_addresses()
    bridge.remote_urls = [f'http://{ip}:{args.port}/remote' for ip in server.lan_hosts]
    if args.no_camera:
        bridge.mode = 'manual'
        bridge.status = 'Camera disabled: use the phone remote'
    if not args.no_camera:
        print('MODEL ' + str(Path(C.SYMBOL_MODEL)), flush=True)
        if not yolo_symbol.has_classifier():
            bridge.model = 'pretrained fallback (custom classifier unavailable)'
        thread = threading.Thread(target=bridge.camera_loop, daemon=True)
        thread.start()
    print(f'Projector: http://127.0.0.1:{args.port}/projector', flush=True)
    print(f'Camera controls: http://127.0.0.1:{args.port}/controls', flush=True)
    for url in bridge.remote_urls:
        print('Phone remote: ' + url, flush=True)
    print('LAN access: allow Python on Private networks if Windows Firewall prompts.', flush=True)
    print('Leave the projector on the extended display. Ctrl+C stops this bridge.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        bridge.stop.set()
        server.server_close()
        if not args.no_camera:
            thread.join(timeout=3)


if __name__ == '__main__':
    main()
