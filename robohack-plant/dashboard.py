import json
import mimetypes
import os
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

try:
    import serial
except ImportError:
    serial = None


HOST = "127.0.0.1"
HTTP_PORT = 8000
BAUD = 115200

BG = "#07120a"
CARD_BG = "#0f1d11"
CARD_EDGE = "#224326"
PANEL_BG = "#132417"
TEXT = "#eaf6ea"
TEXT_DIM = "#86a886"
ACCENT = "#56d364"
ACCENT_2 = "#6ee7b7"
WARN = "#f4b942"
ERROR = "#ef6b6b"


def default_port():
    if os.name == "nt":
        try:
            from serial.tools import list_ports

            for port in list_ports.comports():
                candidate = port.device.lower()
                if "usb" in candidate or "acm" in candidate or "com" in candidate:
                    return port.device
        except Exception:
            pass
        return "COM3"

    try:
        from serial.tools import list_ports

        for port in list_ports.comports():
            candidate = port.device.lower()
            if "ttyusb" in candidate or "ttyacm" in candidate:
                return port.device
    except Exception:
        pass

    return "/dev/ttyUSB0"


def temp_color(temp_c):
    if temp_c < 20:
        return "#5ee06d"
    if temp_c <= 25:
        return "#f4b942"
    return "#ef6b6b"


def moisture_color(pct):
    pct = max(0, min(100, pct))
    if pct <= 50:
        r, g = 255, int(255 * pct / 50)
    else:
        r, g = int(255 * (1 - (pct - 50) / 50)), 255
    return f"#{r:02x}{g:02x}00"


def parse_line(line):
    parts = line.strip().split(",")
    if len(parts) != 3:
        return None
    try:
        light = int(parts[0])
        temp = float(parts[1])
        moisture = int(parts[2])
    except ValueError:
        return None

    return {
        "light": light,
        "temp": temp,
        "moisture": moisture,
        "temp_f": temp * 9 / 5 + 32,
    }


def normalize_history_entry(entry):
    return {
        "light": entry["light"],
        "temp": entry["temp"],
        "temp_f": entry["temp_f"],
        "moisture": entry["moisture"],
        "raw": entry["raw"],
        "timestamp": entry["timestamp"],
        "light_color": entry["light_color"],
        "temp_color": entry["temp_color"],
        "moisture_color": entry["moisture_color"],
        "light_state": entry["light_state"],
        "temp_state": entry["temp_state"],
        "moisture_state": entry["moisture_state"],
    }


class PlantMonitor:
    def __init__(self):
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._serial = None
        self._thread = None
        self._history = []
        self._latest = None
        self._connected = False
        self._port = default_port()
        self._baud = BAUD
        self._status = "Disconnected"
        self._error = None

    def _log(self, message):
        print(message, flush=True)

    def snapshot(self):
        with self._lock:
            latest = None if self._latest is None else dict(self._latest)
            history = [normalize_history_entry(item) for item in self._history[-24:]]
            return {
                "connected": self._connected,
                "port": self._port,
                "baud": self._baud,
                "status": self._status,
                "error": self._error,
                "latest": latest,
                "history": history,
            }

    def connect(self, port, baud):
        self.stop()
        if serial is None:
            error = "pyserial is not installed. Run: pip install pyserial"
            self._log(f"[serial] connection failed: {error}")
            with self._lock:
                self._connected = False
                self._status = error
                self._error = error
                self._port = port
                self._baud = baud
            return False, error

        try:
            serial_port = serial.Serial(port, baud, timeout=1)
        except Exception as exc:
            self._log(f"[serial] connection failed on {port} @ {baud}: {exc}")
            with self._lock:
                self._connected = False
                self._status = f"Connection failed: {exc}"
                self._error = str(exc)
                self._port = port
                self._baud = baud
            return False, str(exc)

        with self._lock:
            self._serial = serial_port
            self._connected = True
            self._port = port
            self._baud = baud
            self._status = "Connected - waiting for data..."
            self._error = None
            self._stop_event.clear()

        self._log(f"[serial] connected on {port} @ {baud}")

        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        return True, None

    def stop(self):
        self._stop_event.set()
        serial_port = None
        thread = None

        with self._lock:
            serial_port = self._serial
            self._serial = None
            thread = self._thread
            self._thread = None
            was_connected = self._connected
            self._connected = False
            if was_connected:
                self._status = "Disconnected"

        if serial_port is not None:
            try:
                serial_port.close()
            except Exception:
                pass

        if was_connected:
          self._log("[serial] disconnected")

        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.5)

    def _read_loop(self):
        while not self._stop_event.is_set():
            with self._lock:
                serial_port = self._serial

            if serial_port is None:
                break

            try:
                raw = serial_port.readline().decode("utf-8", errors="ignore").strip()
                if not raw:
                    continue

                parsed = parse_line(raw)
                if parsed is None:
                    continue

                self._log(
                    f"[serial] raw={raw} | light={parsed['light']}% temp={parsed['temp']:.1f}C moisture={parsed['moisture']}%"
                )

                light_state = "bright" if parsed["light"] >= 80 else "dim"
                temp_state = "cool" if parsed["temp"] < 20 else ("warm" if parsed["temp"] <= 25 else "hot")
                moisture_state = "wet" if parsed["moisture"] >= 60 else ("ok" if parsed["moisture"] >= 30 else "dry")

                entry = {
                    **parsed,
                    "raw": raw,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "light_color": "#f9a825",
                    "temp_color": temp_color(parsed["temp"]),
                    "moisture_color": moisture_color(parsed["moisture"]),
                    "light_state": light_state,
                    "temp_state": temp_state,
                    "moisture_state": moisture_state,
                }

                with self._lock:
                    self._latest = entry
                    self._history.append(entry)
                    self._history = self._history[-120:]
                    self._status = (
                        f"Light: {parsed['light']}%  |  Temp: {parsed['temp']:.1f} °C"
                        f"  |  Moisture: {parsed['moisture']}%"
                    )
                    self._error = None
            except Exception as exc:
              self._log(f"[serial] read error: {exc}")
              with self._lock:
                if self._connected:
                  self._status = "Read error - check connection"
                  self._error = str(exc)
              break

        with self._lock:
            if self._connected:
                self._connected = False
                self._status = "Disconnected"


MONITOR = PlantMonitor()

HTML_PATH = os.path.join(os.path.dirname(__file__), "index.html")


def load_html():
    with open(HTML_PATH, "r", encoding="utf-8") as fh:
        return fh.read()




class DashboardHandler(BaseHTTPRequestHandler):
    monitor = MONITOR

    def log_message(self, format, *args):
        return

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, payload, status=200):
        body = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        route = urlparse(self.path).path

        if route == "/":
            try:
                body = load_html().encode("utf-8")
            except FileNotFoundError:
                body = b"<h1>index.html missing</h1>"
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(body)
            return

        if route == "/api/state":
            self._send_json(self.monitor.snapshot())
            return

        if route == "/api/health":
            self._send_json({"ok": True})
            return
        if route.startswith("/static/"):
            static_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
            relative_path = os.path.normpath(route[len("/static/"):])
            file_path = os.path.abspath(os.path.join(static_root, relative_path))

            if not file_path.startswith(static_root + os.sep) and file_path != static_root:
                self._send_text("Not found", 404)
                return

            if os.path.isfile(file_path):
                try:
                    with open(file_path, "rb") as fh:
                        data = fh.read()
                    content_type, _ = mimetypes.guess_type(file_path)
                    if not content_type:
                        content_type = "application/octet-stream"
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(data)
                    return
                except Exception:
                    pass

        self._send_text("Not found", 404)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0

        payload = {}
        if length:
            raw = self.rfile.read(length).decode("utf-8", errors="ignore")
            if raw:
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    self._send_text("Invalid JSON", 400)
                    return

        if self.path == "/api/connect":
            port = str(payload.get("port") or self.monitor.snapshot()["port"] or default_port())
            try:
                baud = int(payload.get("baud") or BAUD)
            except (TypeError, ValueError):
                self._send_text("Invalid baud rate", 400)
                return

            success, error = self.monitor.connect(port, baud)
            if not success:
                self._send_json({"ok": False, "error": error}, 400)
                return

            self._send_json({"ok": True, "port": port, "baud": baud})
            return

        if self.path == "/api/disconnect":
            self.monitor.stop()
            self._send_json({"ok": True})
            return

        self._send_text("Not found", 404)


def main():
    server = ThreadingHTTPServer((HOST, HTTP_PORT), DashboardHandler)
    print(f"Garden Monitor webapp running at http://{HOST}:{HTTP_PORT}")
    print(f"Default serial port: {DashboardHandler.monitor.snapshot()['port']}")
    try:
      server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        DashboardHandler.monitor.stop()
        server.server_close()


if __name__ == "__main__":
    main()
