#!/usr/bin/env python3
"""
doow-track CLI / daemon binary.

Usage:
  doow-track --api-key dk_...                     # stdin pipe mode
  doow-track --config ./track.json                # file/daemon mode from config
  doow-track --config ./track.json --api-key dk_  # config + key override
  doow-track --version

Pipe mode (stdin):
  echo '{"metric":"builds","quantity":1,"license_id":"lic_1"}' | doow-track --api-key dk_...
  → reads stdin, flushes, exits when stdin closes

Daemon mode:
  doow-track --config ./track.json   (input.mode = file or tcp)
  → runs long-lived, SIGTERM = graceful shutdown, SIGHUP = config reload
"""

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Optional

from ..tracker import Tracker, TrackerOptions
from ..types import TrackEvent
from .sidecar import (
    HealthServer,
    create_input_reader,
    parse_input_mode,
)

VERSION = "0.1.0"


def load_config(config_path: Optional[str]) -> dict[str, Any]:
    """Load config from JSON file."""
    if not config_path:
        return {}

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    return json.loads(path.read_text())


def resolve_config(
    config_path: Optional[str], cli_overrides: dict[str, Any]
) -> dict[str, Any]:
    """Resolve config from file, env, and CLI overrides."""
    config = load_config(config_path)

    # Env overrides
    if api_key := os.environ.get("DOOW_TRACK_API_KEY"):
        config.setdefault("api_key", api_key)
    if endpoint := os.environ.get("DOOW_TRACK_ENDPOINT"):
        config["endpoint"] = endpoint
    if os.environ.get("DOOW_TRACK_DISABLED") == "true":
        config["disabled"] = True
    if os.environ.get("DOOW_TRACK_DEBUG") == "true":
        config["debug"] = True
    if flush_at := os.environ.get("DOOW_TRACK_FLUSH_AT"):
        config["flush_at"] = int(flush_at)
    if flush_interval := os.environ.get("DOOW_TRACK_FLUSH_INTERVAL"):
        config["flush_interval"] = int(flush_interval) / 1000.0
    if attr_json := os.environ.get("DOOW_TRACK_ATTRIBUTION"):
        try:
            config["attribution"] = json.loads(attr_json)
        except Exception:
            pass

    # CLI overrides take priority
    config.update(cli_overrides)

    return config


def build_tracker(config: dict[str, Any]) -> Tracker:
    """Build a Tracker from config."""
    api_key = config.get("api_key", "")
    if not api_key:
        raise ValueError("api_key is required")

    opts = TrackerOptions(
        enabled=not config.get("disabled", False),
        debug=config.get("debug", False),
        on_error=lambda e: print(f"[doow-track] SDK error: {e}", file=sys.stderr),
    )

    if endpoint := config.get("endpoint"):
        opts.endpoint = endpoint
    if attribution := config.get("attribution"):
        opts.attribution = attribution
    if flush_at := config.get("flush_at"):
        opts.flush_at = flush_at
    if flush_interval := config.get("flush_interval"):
        opts.flush_interval = flush_interval

    return Tracker(api_key, opts)


def resolve_input_mode(config: dict[str, Any]) -> Any:
    """Resolve input mode from config or env."""
    if inp := config.get("input"):
        mode = inp.get("mode", "stdin")
        if mode == "stdin":
            return "stdin"
        elif mode == "file":
            path = inp.get("path")
            if not path:
                raise ValueError("input.path required for file mode")
            return ("file", path)
        elif mode == "tcp":
            port = inp.get("port")
            if not port:
                raise ValueError("input.port required for tcp mode")
            return ("tcp", port)

    return parse_input_mode(os.environ.get("DOOW_TRACK_INPUT"))


def write_pid_file(pidfile: str) -> None:
    """Write PID to file."""
    Path(pidfile).write_text(str(os.getpid()))


def remove_pid_file(pidfile: str) -> None:
    """Remove PID file."""
    try:
        Path(pidfile).unlink()
    except Exception:
        pass


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Doow Track CLI / daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--config", "-c", help="Path to JSON config file")
    parser.add_argument("--api-key", "-k", help="API key (overrides config + env)")
    parser.add_argument("--pidfile", help="Write PID to file")
    parser.add_argument(
        "--version", "-v", action="store_true", help="Print version and exit"
    )

    args = parser.parse_args()

    if args.version:
        print(f"doow-track v{VERSION}")
        sys.exit(0)

    # Resolve config
    cli_overrides = {}
    if args.api_key:
        cli_overrides["api_key"] = args.api_key

    try:
        config = resolve_config(args.config, cli_overrides)
    except Exception as e:
        print(f"[doow-track] Config error: {e}", file=sys.stderr)
        sys.exit(1)

    # PID file
    if args.pidfile:
        write_pid_file(args.pidfile)

    # Build tracker
    try:
        tracker = build_tracker(config)
    except ValueError as e:
        print(f"[doow-track] {e}", file=sys.stderr)
        sys.exit(1)

    # Input reader
    try:
        input_mode = resolve_input_mode(config)
    except ValueError as e:
        print(f"[doow-track] {e}", file=sys.stderr)
        sys.exit(1)

    is_daemon = input_mode != "stdin"

    def on_event(raw: str) -> None:
        try:
            data = json.loads(raw)
            tracker.track(TrackEvent(**data))
        except Exception as e:
            print(f"[doow-track] Malformed event — skipping: {e}", file=sys.stderr)

    def on_error(err: Exception, line: str) -> None:
        print(
            f"[doow-track] Malformed line — skipping: {err} | line: {line[:100]}",
            file=sys.stderr,
        )

    reader = create_input_reader(input_mode, on_event, on_error)
    reader.start()

    # Health server for daemon mode
    health: Optional[HealthServer] = None
    if is_daemon:
        health_port = int(config.get("health_port", 9090))
        health = HealthServer(health_port)
        health.start()

    # Graceful shutdown
    shutting_down = False

    def shutdown(signum=None, frame=None) -> None:
        nonlocal shutting_down
        if shutting_down:
            return
        shutting_down = True
        print("[doow-track] Shutting down...", file=sys.stderr)
        reader.stop()
        tracker.shutdown()
        if health:
            health.stop()
        if args.pidfile:
            remove_pid_file(args.pidfile)
        print("[doow-track] Shutdown complete.", file=sys.stderr)
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    # SIGHUP: reload config (daemon mode only)
    def reload_config(signum=None, frame=None) -> None:
        nonlocal tracker, reader, config
        print("[doow-track] SIGHUP — reloading config...", file=sys.stderr)
        try:
            new_config = resolve_config(args.config, cli_overrides)
            new_tracker = build_tracker(new_config)
            new_reader = create_input_reader(input_mode, on_event, on_error)

            # Swap
            old_reader = reader
            old_tracker = tracker
            tracker = new_tracker
            reader = new_reader
            config = new_config

            old_reader.stop()
            old_tracker.shutdown()
            new_reader.start()

            print("[doow-track] Config reloaded.", file=sys.stderr)
        except Exception as e:
            print(f"[doow-track] Config reload failed: {e}", file=sys.stderr)

    if is_daemon:
        signal.signal(signal.SIGHUP, reload_config)
        print(f"[doow-track] Daemon running (PID {os.getpid()}).", file=sys.stderr)

        # Keep alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            shutdown()
    else:
        # Pipe mode: exit when stdin closes
        # The StdinReader will finish when stdin closes
        try:
            while True:
                time.sleep(0.1)
        except (KeyboardInterrupt, EOFError):
            shutdown()


if __name__ == "__main__":
    main()
