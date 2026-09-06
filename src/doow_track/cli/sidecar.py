#!/usr/bin/env python3
"""
Doow Track Sidecar — reads events from stdin/file/tcp and batch-POSTs via Tracker.

Required env:
  DOOW_TRACK_API_KEY          — SDK API key (must start with dk_)

Optional env:
  DOOW_TRACK_INPUT            — stdin (default) | file:<path> | tcp:<port>
  DOOW_TRACK_HEALTH_PORT      — health check port (default 9090)
  DOOW_TRACK_ENDPOINT         — override API endpoint
  DOOW_TRACK_FLUSH_AT         — flush event count threshold
  DOOW_TRACK_FLUSH_INTERVAL   — flush interval ms
  DOOW_TRACK_DISABLED         — disable SDK
  DOOW_TRACK_DEBUG            — enable debug logging
  DOOW_TRACK_ATTRIBUTION      — JSON attribution bag
"""

import json
import os
import signal
import socket
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Callable, Optional, Union

from ..tracker import Tracker, TrackerOptions
from ..types import TrackEvent


# --- Input Readers ---


class InputReader:
    """Base class for input readers."""

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError


class StdinReader(InputReader):
    """Read newline-delimited JSON from stdin."""

    def __init__(self, on_event: Callable[[str], None], on_error: Callable[[Exception, str], None]):
        self._on_event = on_event
        self._on_error = on_error
        self._stopped = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self) -> None:
        for line in sys.stdin:
            if self._stopped:
                break
            line = line.strip()
            if not line:
                continue
            try:
                json.loads(line)  # Validate JSON
                self._on_event(line)
            except Exception as e:
                self._on_error(e, line)

    def stop(self) -> None:
        self._stopped = True


class FileReader(InputReader):
    """Tail a file for newline-delimited JSON."""

    def __init__(
        self,
        file_path: str,
        on_event: Callable[[str], None],
        on_error: Callable[[Exception, str], None],
    ):
        self._file_path = Path(file_path)
        self._on_event = on_event
        self._on_error = on_error
        self._stopped = False
        self._cursor = 0
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def _poll_loop(self) -> None:
        while not self._stopped:
            try:
                if not self._file_path.exists():
                    time.sleep(0.2)
                    continue

                size = self._file_path.stat().st_size
                if size <= self._cursor:
                    time.sleep(0.2)
                    continue

                with open(self._file_path, "r") as f:
                    f.seek(self._cursor)
                    content = f.read()
                    self._cursor = f.tell()

                lines = content.split("\n")
                for line in lines[:-1]:  # All but last (may be incomplete)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        json.loads(line)
                        self._on_event(line)
                    except Exception as e:
                        self._on_error(e, line)

                # Rewind cursor if last line is incomplete
                if lines[-1]:
                    self._cursor -= len(lines[-1].encode("utf-8"))

            except Exception:
                pass
            time.sleep(0.2)

    def stop(self) -> None:
        self._stopped = True


class TcpReader(InputReader):
    """TCP socket server accepting newline-delimited JSON."""

    def __init__(
        self,
        port: int,
        on_event: Callable[[str], None],
        on_error: Callable[[Exception, str], None],
    ):
        self._port = port
        self._on_event = on_event
        self._on_error = on_error
        self._server: Optional[socket.socket] = None
        self._stopped = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("0.0.0.0", self._port))
        self._server.listen(10)
        self._server.settimeout(1.0)

        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def _accept_loop(self) -> None:
        while not self._stopped and self._server:
            try:
                conn, _ = self._server.accept()
                threading.Thread(
                    target=self._handle_connection, args=(conn,), daemon=True
                ).start()
            except socket.timeout:
                continue
            except Exception:
                break

    def _handle_connection(self, conn: socket.socket) -> None:
        conn.settimeout(60.0)
        buf = ""
        try:
            while not self._stopped:
                data = conn.recv(4096)
                if not data:
                    break
                buf += data.decode("utf-8")

                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        json.loads(line)
                        self._on_event(line)
                    except Exception as e:
                        self._on_error(e, line)
        except Exception:
            pass
        finally:
            conn.close()

    def stop(self) -> None:
        self._stopped = True
        if self._server:
            self._server.close()
            self._server = None


def parse_input_mode(
    env_value: Optional[str],
) -> Union[str, tuple[str, str], tuple[str, int]]:
    """Parse DOOW_TRACK_INPUT env var."""
    if not env_value or env_value == "stdin":
        return "stdin"

    if env_value.startswith("file:"):
        path = env_value[5:]
        if not path:
            raise ValueError("DOOW_TRACK_INPUT file: mode requires a path")
        return ("file", path)

    if env_value.startswith("tcp:"):
        port_str = env_value[4:]
        try:
            port = int(port_str)
            if port < 1 or port > 65535:
                raise ValueError()
            return ("tcp", port)
        except ValueError:
            raise ValueError("DOOW_TRACK_INPUT tcp: mode requires a valid port")

    raise ValueError(
        f'Unknown DOOW_TRACK_INPUT: "{env_value}". Use stdin, file:<path>, or tcp:<port>'
    )


def create_input_reader(
    mode: Union[str, tuple[str, str], tuple[str, int]],
    on_event: Callable[[str], None],
    on_error: Callable[[Exception, str], None],
) -> InputReader:
    """Create an input reader based on mode."""
    if mode == "stdin":
        return StdinReader(on_event, on_error)
    elif isinstance(mode, tuple):
        if mode[0] == "file":
            return FileReader(mode[1], on_event, on_error)
        elif mode[0] == "tcp":
            return TcpReader(mode[1], on_event, on_error)
    raise ValueError(f"Unknown input mode: {mode}")


# --- Health Server ---


class HealthHandler(BaseHTTPRequestHandler):
    """Simple health check handler."""

    def do_GET(self) -> None:
        if self.path == "/healthz" or self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format: str, *args) -> None:
        pass  # Suppress logs


class HealthServer:
    """HTTP health check server."""

    def __init__(self, port: int):
        self._port = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._server = HTTPServer(("0.0.0.0", self._port), HealthHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server = None


# --- Main ---


def main() -> None:
    """Sidecar entry point."""
    api_key = os.environ.get("DOOW_TRACK_API_KEY")
    if not api_key:
        print("[doow-sidecar] DOOW_TRACK_API_KEY is required", file=sys.stderr)
        sys.exit(1)

    # Parse attribution from env
    attribution = {}
    if attr_json := os.environ.get("DOOW_TRACK_ATTRIBUTION"):
        try:
            attribution = json.loads(attr_json)
        except Exception:
            pass

    # Build tracker
    tracker = Tracker(
        api_key,
        TrackerOptions(
            attribution=attribution,
            on_error=lambda e: print(f"[doow-sidecar] SDK error: {e}", file=sys.stderr),
        ),
    )

    # Health server
    health_port = int(os.environ.get("DOOW_TRACK_HEALTH_PORT", "9090"))
    health = HealthServer(health_port)
    health.start()

    # Input reader
    input_mode = parse_input_mode(os.environ.get("DOOW_TRACK_INPUT"))

    def on_event(raw: str) -> None:
        try:
            data = json.loads(raw)
            tracker.track(TrackEvent(**data))
        except Exception as e:
            print(f"[doow-sidecar] Malformed event — skipping: {e}", file=sys.stderr)

    def on_error(err: Exception, line: str) -> None:
        print(
            f"[doow-sidecar] Malformed line — skipping: {err} | line: {line[:100]}",
            file=sys.stderr,
        )

    reader = create_input_reader(input_mode, on_event, on_error)
    reader.start()

    # Graceful shutdown
    shutting_down = False

    def shutdown(signum=None, frame=None) -> None:
        nonlocal shutting_down
        if shutting_down:
            return
        shutting_down = True
        print("[doow-sidecar] Shutting down...", file=sys.stderr)
        reader.stop()
        tracker.shutdown()
        health.stop()
        print("[doow-sidecar] Shutdown complete.", file=sys.stderr)
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    print(
        f"[doow-sidecar] Running. Health: http://localhost:{health_port}/healthz",
        file=sys.stderr,
    )

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
