"""Telemetry tracker for Doow SDK."""

import asyncio
import gzip
import json
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import httpx

from .errors import APIError
from .types import EventKind, RateLimit, SerializedEvent, TrackEvent

SDK_VERSION = "0.1.0"
DEFAULT_ENDPOINT = "https://api.doow.co"
DEFAULT_FLUSH_AT = 20
DEFAULT_FLUSH_INTERVAL = 10.0
DEFAULT_MAX_PAYLOAD = 450 * 1024
DEFAULT_MAX_QUEUE_SIZE = 10000
DEFAULT_TIMEOUT = 10.0
DEFAULT_RETRY_COUNT = 3
DEFAULT_SHUTDOWN_TIMEOUT = 5.0


@dataclass
class TrackerOptions:
    """Configuration options for Tracker."""

    endpoint: str = DEFAULT_ENDPOINT
    enabled: bool = True
    debug: bool = False
    flush_at: int = DEFAULT_FLUSH_AT
    flush_interval: float = DEFAULT_FLUSH_INTERVAL
    max_payload_bytes: int = DEFAULT_MAX_PAYLOAD
    max_queue_size: int = DEFAULT_MAX_QUEUE_SIZE
    timeout: float = DEFAULT_TIMEOUT
    retry_count: int = DEFAULT_RETRY_COUNT
    shutdown_timeout: float = DEFAULT_SHUTDOWN_TIMEOUT
    disable_compression: bool = False
    attribution: dict[str, Any] = field(default_factory=dict)
    on_error: Optional[Callable[[Exception], None]] = None
    before_send: Optional[Callable[[SerializedEvent], Optional[SerializedEvent]]] = None
    before_flush: Optional[Callable[[list[SerializedEvent]], list[SerializedEvent]]] = None
    offline_store: Optional["OfflineStore"] = None


class OfflineStore:
    """Interface for offline batch storage."""

    def push(self, batch: dict) -> None:
        raise NotImplementedError

    def shift(self) -> Optional[dict]:
        raise NotImplementedError

    def length(self) -> int:
        raise NotImplementedError


class FileOfflineStore(OfflineStore):
    """File-based offline storage."""

    def __init__(self, directory: Optional[str] = None):
        if directory:
            self.directory = Path(directory)
        else:
            self.directory = Path.home() / ".doow" / "offline"
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def push(self, batch: dict) -> None:
        with self._lock:
            filename = f"{batch.get('batch_id', uuid.uuid4().hex)}.json"
            filepath = self.directory / filename
            filepath.write_text(json.dumps(batch))

    def shift(self) -> Optional[dict]:
        with self._lock:
            files = sorted(self.directory.glob("*.json"))
            if not files:
                return None
            filepath = files[0]
            data = json.loads(filepath.read_text())
            filepath.unlink()
            return data

    def length(self) -> int:
        return len(list(self.directory.glob("*.json")))


class Tracker:
    """Telemetry tracker with batching, compression, and retries."""

    def __init__(self, api_key: str, options: Optional[TrackerOptions] = None):
        self._options = options or TrackerOptions()
        self._api_key = os.environ.get("DOOW_TRACK_API_KEY", api_key)

        # Environment overrides
        if env_endpoint := os.environ.get("DOOW_TRACK_ENDPOINT"):
            self._options.endpoint = env_endpoint
        if os.environ.get("DOOW_TRACK_DISABLED") == "true":
            self._options.enabled = False
        if os.environ.get("DOOW_TRACK_DEBUG") == "true":
            self._options.debug = True
        if env_flush_at := os.environ.get("DOOW_TRACK_FLUSH_AT"):
            self._options.flush_at = int(env_flush_at)
        if env_interval := os.environ.get("DOOW_TRACK_FLUSH_INTERVAL"):
            self._options.flush_interval = int(env_interval) / 1000.0

        self._buffer: list[SerializedEvent] = []
        self._lock = threading.Lock()
        self._shutdown = threading.Event()
        self._rate_limit: Optional[RateLimit] = None
        self._client = httpx.Client(timeout=self._options.timeout)

        # Start flush loop
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()

        # Drain offline store
        if self._options.offline_store:
            threading.Thread(target=self._drain_offline_store, daemon=True).start()

    def _log(self, message: str) -> None:
        if self._options.debug:
            print(f"[doow/track] {message}")

    def track(self, event: TrackEvent) -> None:
        """Queue an event for submission."""
        if not self._options.enabled:
            return
        if self._shutdown.is_set():
            return

        # Generate event ID and timestamp
        timestamp = event.timestamp or datetime.utcnow()
        timestamp_str = timestamp.isoformat() + "Z" if not timestamp.isoformat().endswith("Z") else timestamp.isoformat()

        # Merge attribution
        attribution = {**self._options.attribution, **(event.attribution or {})}

        serialized = SerializedEvent(
            event_id=str(uuid.uuid4()),
            metric=event.metric,
            quantity=event.quantity,
            license_id=event.license_id,
            unit=event.unit,
            kind=event.kind,
            timestamp=timestamp_str,
            source_system=event.source_system,
            metric_tuple_hint=event.metric_tuple_hint,
            attribution=attribution if attribution else None,
            metadata=event.metadata,
        )

        # BeforeSend hook
        if self._options.before_send:
            result = self._options.before_send(serialized)
            if result is None:
                self._log("event dropped by before_send hook")
                return
            serialized = result

        with self._lock:
            if len(self._buffer) >= self._options.max_queue_size:
                self._buffer.pop(0)
                self._log("queue full, dropped oldest event")
            self._buffer.append(serialized)
            should_flush = len(self._buffer) >= self._options.flush_at

        if should_flush:
            threading.Thread(target=self.flush, daemon=True).start()

    def flush(self) -> None:
        """Send all buffered events immediately."""
        with self._lock:
            if not self._buffer:
                return
            events = self._buffer.copy()
            self._buffer.clear()

        # BeforeFlush hook
        if self._options.before_flush:
            events = self._options.before_flush(events)
            if not events:
                self._log("batch dropped by before_flush hook")
                return

        self._send_batch(events)

    def _send_batch(self, events: list[SerializedEvent]) -> None:
        batch_id = str(uuid.uuid4())

        # Convert to wire format
        wire_events = []
        for e in events:
            source_system = e.source_system or "sdk"
            wire_events.append({
                "event_id": e.event_id,
                "license_id": e.license_id,
                "occurred_at": e.timestamp,
                "source_system": source_system,
                "kind": e.kind.value if isinstance(e.kind, EventKind) else e.kind,
                "attribution": e.attribution,
                "metadata": e.metadata,
                "measurements": [{
                    "metric_name": e.metric,
                    "quantity": e.quantity,
                    "metric_tuple_hint": e.metric_tuple_hint,
                }],
            })

        payload = {
            "batch_id": batch_id,
            "sdk_version": SDK_VERSION,
            "events": wire_events,
        }

        body = json.dumps(payload).encode()
        self._log(f"sending batch {batch_id} with {len(events)} events ({len(body)} bytes)")

        # Retry loop
        last_error: Optional[Exception] = None
        for attempt in range(self._options.retry_count + 1):
            if attempt > 0:
                backoff = min(0.1 * (2 ** (attempt - 1)), 10.0)
                self._log(f"retry attempt {attempt} after {backoff}s")
                threading.Event().wait(backoff)

            try:
                error = self._do_send(body)
                if error is None:
                    self._log(f"batch {batch_id} sent successfully")
                    return
                last_error = error

                if isinstance(error, APIError):
                    if error.status in (401, 403):
                        break  # Not retryable
                    if error.status == 429:
                        threading.Event().wait(5.0)
            except Exception as e:
                last_error = e

        # All retries failed - try offline store
        if self._options.offline_store and last_error:
            try:
                self._options.offline_store.push({
                    "batch_id": batch_id,
                    "payload": json.dumps(payload),
                    "timestamp": datetime.utcnow().isoformat(),
                })
                self._log(f"batch {batch_id} saved to offline store")
            except Exception as e:
                self._handle_error(e)

        if last_error and self._options.on_error:
            self._options.on_error(last_error)

    def _do_send(self, body: bytes) -> Optional[Exception]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"doow-track-python/{SDK_VERSION}",
        }

        # Compress if needed
        if not self._options.disable_compression and len(body) > 1024:
            body = gzip.compress(body)
            headers["Content-Encoding"] = "gzip"

        try:
            response = self._client.post(
                f"{self._options.endpoint}/telemetry/events",
                content=body,
                headers=headers,
            )

            # Parse rate limit headers
            if limit := response.headers.get("X-RateLimit-Limit"):
                self._rate_limit = RateLimit(
                    limit=int(limit),
                    remaining=int(response.headers.get("X-RateLimit-Remaining", 0)),
                    reset=datetime.fromtimestamp(
                        int(response.headers.get("X-RateLimit-Reset", 0))
                    ),
                )

            if response.status_code >= 400:
                try:
                    data = response.json()
                    return APIError(
                        status=response.status_code,
                        message=data.get("message", response.reason_phrase),
                        error_class=data.get("errorClass"),
                        details=data,
                    )
                except Exception:
                    return APIError(
                        status=response.status_code,
                        message=response.reason_phrase,
                    )

            return None
        except Exception as e:
            return e  # type: ignore

    def _flush_loop(self) -> None:
        while not self._shutdown.wait(self._options.flush_interval):
            try:
                self.flush()
            except Exception as e:
                self._handle_error(e)

    def _drain_offline_store(self) -> None:
        if not self._options.offline_store:
            return
        while True:
            batch = self._options.offline_store.shift()
            if not batch:
                return
            try:
                payload = json.loads(batch["payload"])
                body = json.dumps(payload).encode()
                error = self._do_send(body)
                if error:
                    self._options.offline_store.push(batch)
                    return
                self._log(f"drained offline batch {batch.get('batch_id')}")
            except Exception:
                self._options.offline_store.push(batch)
                return

    def _handle_error(self, error: Exception) -> None:
        if self._options.on_error:
            self._options.on_error(error)
        elif self._options.debug:
            print(f"[doow/track] error: {error}")

    def shutdown(self, timeout: Optional[float] = None) -> None:
        """Flush remaining events and stop the tracker."""
        self._shutdown.set()
        self.flush()
        timeout = timeout or self._options.shutdown_timeout
        self._flush_thread.join(timeout=timeout)
        self._client.close()

    @property
    def rate_limit(self) -> Optional[RateLimit]:
        """Get the last known rate limit info."""
        return self._rate_limit

    def __enter__(self) -> "Tracker":
        return self

    def __exit__(self, *args: Any) -> None:
        self.shutdown()


class AsyncTracker:
    """Async version of the telemetry tracker."""

    def __init__(self, api_key: str, options: Optional[TrackerOptions] = None):
        self._options = options or TrackerOptions()
        self._api_key = os.environ.get("DOOW_TRACK_API_KEY", api_key)

        # Environment overrides
        if env_endpoint := os.environ.get("DOOW_TRACK_ENDPOINT"):
            self._options.endpoint = env_endpoint
        if os.environ.get("DOOW_TRACK_DISABLED") == "true":
            self._options.enabled = False
        if os.environ.get("DOOW_TRACK_DEBUG") == "true":
            self._options.debug = True

        self._buffer: list[SerializedEvent] = []
        self._lock = asyncio.Lock()
        self._shutdown = False
        self._rate_limit: Optional[RateLimit] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._flush_task: Optional[asyncio.Task] = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._options.timeout)
            self._flush_task = asyncio.create_task(self._flush_loop())
        return self._client

    def _log(self, message: str) -> None:
        if self._options.debug:
            print(f"[doow/track] {message}")

    async def track(self, event: TrackEvent) -> None:
        """Queue an event for submission."""
        if not self._options.enabled or self._shutdown:
            return

        await self._ensure_client()

        timestamp = event.timestamp or datetime.utcnow()
        timestamp_str = timestamp.isoformat() + "Z"

        attribution = {**self._options.attribution, **(event.attribution or {})}

        serialized = SerializedEvent(
            event_id=str(uuid.uuid4()),
            metric=event.metric,
            quantity=event.quantity,
            license_id=event.license_id,
            unit=event.unit,
            kind=event.kind,
            timestamp=timestamp_str,
            source_system=event.source_system,
            metric_tuple_hint=event.metric_tuple_hint,
            attribution=attribution if attribution else None,
            metadata=event.metadata,
        )

        if self._options.before_send:
            result = self._options.before_send(serialized)
            if result is None:
                return
            serialized = result

        async with self._lock:
            if len(self._buffer) >= self._options.max_queue_size:
                self._buffer.pop(0)
            self._buffer.append(serialized)
            should_flush = len(self._buffer) >= self._options.flush_at

        if should_flush:
            asyncio.create_task(self.flush())

    async def flush(self) -> None:
        """Send all buffered events immediately."""
        async with self._lock:
            if not self._buffer:
                return
            events = self._buffer.copy()
            self._buffer.clear()

        if self._options.before_flush:
            events = self._options.before_flush(events)
            if not events:
                return

        await self._send_batch(events)

    async def _send_batch(self, events: list[SerializedEvent]) -> None:
        batch_id = str(uuid.uuid4())

        wire_events = []
        for e in events:
            wire_events.append({
                "event_id": e.event_id,
                "license_id": e.license_id,
                "occurred_at": e.timestamp,
                "source_system": e.source_system or "sdk",
                "kind": e.kind.value if isinstance(e.kind, EventKind) else e.kind,
                "attribution": e.attribution,
                "metadata": e.metadata,
                "measurements": [{
                    "metric_name": e.metric,
                    "quantity": e.quantity,
                    "metric_tuple_hint": e.metric_tuple_hint,
                }],
            })

        payload = {
            "batch_id": batch_id,
            "sdk_version": SDK_VERSION,
            "events": wire_events,
        }

        body = json.dumps(payload).encode()
        self._log(f"sending batch {batch_id} with {len(events)} events")

        client = await self._ensure_client()
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"doow-track-python/{SDK_VERSION}",
        }

        if not self._options.disable_compression and len(body) > 1024:
            body = gzip.compress(body)
            headers["Content-Encoding"] = "gzip"

        for attempt in range(self._options.retry_count + 1):
            if attempt > 0:
                await asyncio.sleep(min(0.1 * (2 ** (attempt - 1)), 10.0))

            try:
                response = await client.post(
                    f"{self._options.endpoint}/telemetry/events",
                    content=body,
                    headers=headers,
                )
                if response.status_code < 400:
                    self._log(f"batch {batch_id} sent successfully")
                    return
                if response.status_code in (401, 403):
                    break
            except Exception as e:
                if self._options.on_error:
                    self._options.on_error(e)

    async def _flush_loop(self) -> None:
        while not self._shutdown:
            await asyncio.sleep(self._options.flush_interval)
            try:
                await self.flush()
            except Exception:
                pass

    async def shutdown(self) -> None:
        """Flush and close."""
        self._shutdown = True
        await self.flush()
        if self._flush_task:
            self._flush_task.cancel()
        if self._client:
            await self._client.aclose()

    async def __aenter__(self) -> "AsyncTracker":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.shutdown()
