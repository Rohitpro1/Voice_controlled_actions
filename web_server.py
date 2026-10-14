"""Local HTTP dashboard and Nikki Streams bridge for VoiceLight.

Binds only to loopback. The existing main.py is read for its configured SDK
session value but is never imported, edited, or launched by this server.
"""
import ast
import asyncio
import json
import logging
import mimetypes
import re
import signal
from collections import deque
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from nikki_streams import SDK

ROOT = Path(__file__).resolve().parent
HOST = "127.0.0.1"
PORT = 8000
MAX_BODY = 16_384
LOG = logging.getLogger("voicelight")


def read_existing_session_id():
    """Read SESSION_ID from main.py without importing or exposing its value."""
    tree = ast.parse((ROOT / "main.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "SESSION_ID"
            for target in node.targets
        ) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            if node.value.value.strip():
                return node.value.value
    raise RuntimeError("Could not read a string SESSION_ID from main.py")


class VoiceLight:
    def __init__(self):
        self.device = None
        self.phone_status = "disconnected"
        self.last_error = None
        self.flashlight_on = None
        self.voice_task = None
        self.voice_stop = None
        self.last_command = None
        self.logs = deque(maxlen=80)
        self.notification_history = deque(maxlen=500)
        self.lock = asyncio.Lock()

    def log(self, message, level="info", detail=""):
        entry = {
            "time": datetime.now().astimezone().strftime("%H:%M:%S"),
            "message": str(message)[:180],
            "level": level if level in ("info", "success", "error") else "info",
            "detail": str(detail)[:240],
        }
        self.logs.append(entry)
        LOG.info("%s%s", entry["message"], f": {entry['detail']}" if entry["detail"] else "")

    def on_device_event(self, event):
        if getattr(event, "type", None) == "statusChange":
            status = str(getattr(event, "data", "disconnected")).lower()
            self.phone_status = "connected" if status == "connected" else "disconnected"
            error = getattr(event, "error", None)
            self.last_error = str(error)[:240] if error else None
            self.log(
                "Phone connected" if self.phone_status == "connected" else "Phone disconnected",
                "success" if self.phone_status == "connected" else ("error" if error else "info"),
                self.last_error or "Nikki Streams connection status changed",
            )

    def status(self):
        voice_listening = bool(self.voice_task and not self.voice_task.done())
        return {
            "backend_running": True,
            "phone_connected": bool(self.device and self.device.is_connected),
            "phone_status": self.phone_status,
            "message": self.last_error or ("Phone is ready for controls." if self.phone_status == "connected" else "Phone is not connected."),
            "flashlight_on": self.flashlight_on,
            "voice_listening": voice_listening,
            "last_command": self.last_command,
        }

    async def connect(self):
        self.phone_status = "connecting"
        self.last_error = None
        try:
            if self.device is None:
                # Use the existing address from the user's working app.
                self.device = SDK.create_device("192.168.29.101:3000", self.on_device_event)
            if not self.device.is_connected:
                await self.device.connect()
            self.phone_status = "connected"
            self.last_error = None
            return True
        except Exception as error:
            self.phone_status = "disconnected"
            self.last_error = str(error)[:240]
            self.log("Phone connection failed", "error", self.last_error)
            return False

    async def perform(self, action, data, source="website"):
        async with self.lock:
            if not self.device or not self.device.is_connected:
                raise RuntimeError("Phone is not connected. Check Nikki Streams and reconnect.")
            if action == "flashlight":
                if not isinstance(data.get("on"), bool):
                    raise ValueError("The 'on' field must be true or false.")
                await self.device.set_light_status(data["on"])
                self.flashlight_on = data["on"]
                message = f"Flashlight {'ON' if data['on'] else 'OFF'} command sent; phone confirmation is unavailable"
            elif action == "notification":
                title = data.get("title")
                body = data.get("message")
                if not isinstance(title, str) or not title.strip() or len(title.strip()) > 80:
                    raise ValueError("Title is required and must be 80 characters or fewer.")
                if not isinstance(body, str) or not body.strip() or len(body.strip()) > 300:
                    raise ValueError("Message is required and must be 300 characters or fewer.")
                await self.device.set_notification(title.strip(), body.strip())
                message = "Notification command sent"
                self.notification_history.append({
                    "time": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S"),
                    "title": title.strip(),
                    "message": body.strip(),
                    "source": source,
                })
                self.log(message, "success", f"{title.strip()}: {body.strip()}")
                return {"ok": True, "message": message}
            else:
                raise ValueError("Unsupported command.")
            self.log(message, "success")
            return {"ok": True, "message": message}

    async def start_voice(self):
        if self.voice_task and not self.voice_task.done():
            return {"ok": True, "message": "Voice control is already listening"}
        if not self.device or not self.device.is_connected:
            raise RuntimeError("Phone is not connected.")
        try:
            import speech_recognition as sr
            recognizer = sr.Recognizer()
            microphone = sr.Microphone()
        except Exception as error:
            raise RuntimeError(f"Microphone setup failed: {error}") from error
        self.voice_stop = asyncio.Event()
        self.voice_task = asyncio.create_task(self.voice_loop(sr, recognizer, microphone))
        self.log("Voice control started", "success", "Listening on the computer microphone")
        return {"ok": True, "message": "Voice control started"}

    async def voice_loop(self, sr, recognizer, microphone):
        try:
            while not self.voice_stop.is_set():
                try:
                    text = await asyncio.to_thread(self.listen_once, sr, recognizer, microphone)
                    self.last_command = text
                    self.log("Voice command recognized", "info", text)
                    intent = classify_voice_command(text)
                    if intent == "light_on":
                        await self.perform("flashlight", {"on": True})
                    elif intent == "light_off":
                        await self.perform("flashlight", {"on": False})
                    elif intent == "notification":
                        notification = parse_voice_notification(text)
                        if notification is None:
                            self.log("Voice notification needs a message", "error", "Say: send notification followed by your message")
                        else:
                            await self.perform("notification", notification, source="voice control")
                    else:
                        self.log("Voice command not recognized", "info", text)
                except sr.WaitTimeoutError:
                    continue
                except sr.UnknownValueError:
                    self.log("Speech not understood", "info", "Please try again")
                except sr.RequestError as error:
                    self.log("Speech recognition error", "error", error)
                    await asyncio.sleep(1)
                except Exception as error:
                    self.log("Voice command failed", "error", error)
        except asyncio.CancelledError:
            raise

    @staticmethod
    def listen_once(sr, recognizer, microphone):
        with microphone as source:
            audio = recognizer.listen(source, timeout=2, phrase_time_limit=5)
        return recognizer.recognize_google(audio).lower()

    async def stop_voice(self):
        if not self.voice_task or self.voice_task.done():
            self.voice_task = None
            return {"ok": True, "message": "Voice control is not listening"}
        self.voice_stop.set()
        try:
            await asyncio.wait_for(self.voice_task, timeout=8)
        except asyncio.TimeoutError:
            self.voice_task.cancel()
            await asyncio.gather(self.voice_task, return_exceptions=True)
        self.voice_task = None
        self.log("Voice control stopped", "info")
        return {"ok": True, "message": "Voice control stopped"}

    async def shutdown(self):
        if self.voice_task and not self.voice_task.done():
            await self.stop_voice()
        if self.device and self.device.is_connected:
            await self.device.disconnect()


def classify_voice_command(text):
    """Map common spoken phrases to a flashlight or notification action."""
    command = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    command = re.sub(r"\s+", " ", command).strip()
    if re.search(r"\bsend\s+(?:a\s+)?notification\b", command):
        return "notification"

    device = r"(?:flash\s*light|lights?)"
    before_device = rf"(?:the\s+|my\s+|phone\s+|phone\s+)?{device}"
    patterns = (
        ("light_on", rf"\b(?:turn|switch|power)\s+on\s+{before_device}\b"),
        ("light_off", rf"\b(?:turn|switch|power)\s+off\s+{before_device}\b"),
        ("light_on", rf"\b(?:turn|switch|power)\s+{before_device}\s+on\b"),
        ("light_off", rf"\b(?:turn|switch|power)\s+{before_device}\s+off\b"),
        ("light_on", rf"\b{device}\s+(?:is\s+)?on\b"),
        ("light_off", rf"\b{device}\s+(?:is\s+)?off\b"),
        ("light_on", rf"\b(?:activate|enable)\s+{before_device}\b"),
        ("light_off", rf"\b(?:deactivate|disable)\s+{before_device}\b"),
    )
    for intent, pattern in patterns:
        if re.search(pattern, command):
            return intent
    return None


def parse_voice_notification(command):
    """Accept 'send notification <text>' or 'send notification title X message Y'."""
    match = re.match(r"^send\s+(?:a\s+)?notification\b\s*(.*)$", command.strip(), re.IGNORECASE)
    if not match:
        return None
    content = match.group(1).strip()
    if not content:
        return None
    titled = re.match(r"^title\s+(.+?)\s+message\s+(.+)$", content, re.IGNORECASE)
    if titled:
        title, message = titled.group(1).strip(), titled.group(2).strip()
    else:
        title, message = "VoiceLight", re.sub(r"^message\s+", "", content, flags=re.IGNORECASE).strip()
    if not title or not message or len(title) > 80 or len(message) > 300:
        return None
    return {"title": title, "message": message}

app = VoiceLight()


def json_response(status, payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    phrase = {200: "OK", 400: "Bad Request", 403: "Forbidden", 404: "Not Found", 405: "Method Not Allowed", 413: "Payload Too Large", 500: "Internal Server Error"}.get(status, "Error")
    return (
        f"HTTP/1.1 {status} {phrase}\r\n"
        "Content-Type: application/json; charset=utf-8\r\n"
        f"Content-Length: {len(data)}\r\n"
        "Cache-Control: no-store\r\n"
        "X-Content-Type-Options: nosniff\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii") + data


async def read_request(reader):
    head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5)
    if len(head) > 8192:
        raise ValueError("Request headers too large")
    lines = head.decode("iso-8859-1").split("\r\n")
    method, target, _version = lines[0].split(" ", 2)
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    if length < 0 or length > MAX_BODY:
        raise OverflowError("Request body too large")
    body = await asyncio.wait_for(reader.readexactly(length), timeout=5) if length else b""
    return method.upper(), target, headers, body


async def handle_client(reader, writer):
    try:
        try:
            method, target, headers, raw_body = await read_request(reader)
        except OverflowError:
            writer.write(json_response(413, {"error": "Request body too large"})); await writer.drain(); return
        except Exception:
            writer.write(json_response(400, {"error": "Malformed HTTP request"})); await writer.drain(); return

        host = headers.get("host", "").lower()
        origin = headers.get("origin")
        allowed_hosts = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
        if host not in allowed_hosts or (origin and origin not in {f"http://{h}" for h in allowed_hosts}):
            writer.write(json_response(403, {"error": "Local requests only"})); await writer.drain(); return

        path = urlsplit(target).path
        try:
            if path.startswith("/api/"):
                if method == "GET" and path == "/api/status":
                    result = app.status()
                elif method == "GET" and path == "/api/logs":
                    result = {"logs": list(app.logs)}
                elif method == "GET" and path == "/api/notifications":
                    result = {"notifications": list(app.notification_history)}
                elif method == "POST":
                    try:
                        data = json.loads(raw_body or b"{}")
                        if not isinstance(data, dict):
                            raise ValueError("Expected a JSON object")
                    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
                        raise ValueError(f"Invalid JSON: {error}") from error
                    if path == "/api/flashlight": result = await app.perform("flashlight", data)
                    elif path == "/api/notification": result = await app.perform("notification", data)
                    elif path == "/api/voice/start": result = await app.start_voice()
                    elif path == "/api/voice/stop": result = await app.stop_voice()
                    elif path == "/api/reconnect":
                        ok = await app.connect()
                        if not ok: raise RuntimeError(app.last_error or "Phone connection failed")
                        result = {"ok": True, "message": "Phone connected"}
                    else:
                        writer.write(json_response(404, {"error": "Unknown API endpoint"})); await writer.drain(); return
                else:
                    writer.write(json_response(405, {"error": "Method not allowed"})); await writer.drain(); return
                writer.write(json_response(200, result))
            elif method in ("GET", "HEAD"):
                filename = {"/": "index.html", "/index.html": "index.html", "/style.css": "style.css", "/script.js": "script.js"}.get(path)
                if not filename:
                    writer.write(json_response(404, {"error": "Not found"})); await writer.drain(); return
                content = (ROOT / filename).read_bytes()
                content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
                writer.write((f"HTTP/1.1 200 OK\r\nContent-Type: {content_type}; charset=utf-8\r\nContent-Length: {len(content)}\r\nCache-Control: no-cache\r\nX-Content-Type-Options: nosniff\r\nConnection: close\r\n\r\n").encode("ascii"))
                if method != "HEAD": writer.write(content)
            else:
                writer.write(json_response(405, {"error": "Method not allowed"}))
        except (ValueError, RuntimeError) as error:
            app.log("Request failed", "error", error)
            writer.write(json_response(400, {"error": str(error)}))
        except Exception as error:
            app.log("Backend operation failed", "error", error)
            writer.write(json_response(500, {"error": "Backend operation failed"}))
        await writer.drain()
    except (ConnectionError, asyncio.IncompleteReadError, asyncio.TimeoutError):
        pass
    finally:
        writer.close()
        try: await writer.wait_closed()
        except ConnectionError: pass


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    SDK.initialize(read_existing_session_id())
    server = await asyncio.start_server(handle_client, HOST, PORT, limit=20_000)
    app.log("Backend started", "success", f"Dashboard at http://{HOST}:{PORT}")
    print(f"VoiceLight dashboard: http://{HOST}:{PORT}")
    print("This service is bound to this Mac only. Press Ctrl+C to stop.")
    connected = await app.connect()
    if not connected:
        print("Phone is not connected yet; check Nikki Streams, then use Refresh status.")
    async with server:
        try:
            await server.serve_forever()
        finally:
            await app.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("VoiceLight stopped.")
