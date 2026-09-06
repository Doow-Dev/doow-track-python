"""Tests for Tracker."""

import json
import time

import pytest
from pytest_httpx import HTTPXMock

from doow_track import Tracker, TrackerOptions, TrackEvent


def test_tracker_track_and_flush(httpx_mock: HTTPXMock):
    """Test tracking events and flushing."""
    received_batches = []

    def capture_request(request):
        body = json.loads(request.content)
        received_batches.append(body)
        return httpx_mock.Response(status_code=200)

    httpx_mock.add_callback(capture_request, url="https://test.doow.co/telemetry/events")

    tracker = Tracker("dk_test_key", TrackerOptions(
        endpoint="https://test.doow.co",
        flush_at=2,
        flush_interval=100.0,
        debug=True,
    ))

    tracker.track(TrackEvent(metric="api_calls", quantity=1, license_id="lic_123"))
    tracker.track(TrackEvent(metric="api_calls", quantity=2, license_id="lic_123"))

    time.sleep(0.5)
    tracker.shutdown()

    assert len(received_batches) >= 1
    batch = received_batches[0]
    assert len(batch["events"]) == 2
    assert batch["sdk_version"] == "0.1.0"


def test_tracker_before_send_hook(httpx_mock: HTTPXMock):
    """Test before_send hook can drop events."""
    received_batches = []

    def capture_request(request):
        body = json.loads(request.content)
        received_batches.append(body)
        return httpx_mock.Response(status_code=200)

    httpx_mock.add_callback(capture_request, url="https://test.doow.co/telemetry/events")

    def before_send(event):
        if event.quantity == 0:
            return None
        return event

    tracker = Tracker("dk_test_key", TrackerOptions(
        endpoint="https://test.doow.co",
        flush_at=10,
        flush_interval=100.0,
        before_send=before_send,
    ))

    tracker.track(TrackEvent(metric="test", quantity=0, license_id="lic_1"))
    tracker.track(TrackEvent(metric="test", quantity=5, license_id="lic_1"))

    tracker.flush()
    time.sleep(0.1)
    tracker.shutdown()

    assert len(received_batches) == 1
    assert len(received_batches[0]["events"]) == 1
    assert received_batches[0]["events"][0]["measurements"][0]["quantity"] == 5


def test_tracker_attribution(httpx_mock: HTTPXMock):
    """Test SDK-level attribution is merged."""
    received_batches = []

    def capture_request(request):
        body = json.loads(request.content)
        received_batches.append(body)
        return httpx_mock.Response(status_code=200)

    httpx_mock.add_callback(capture_request, url="https://test.doow.co/telemetry/events")

    tracker = Tracker("dk_test_key", TrackerOptions(
        endpoint="https://test.doow.co",
        flush_at=1,
        attribution={"service": "test-service", "version": "1.0.0"},
    ))

    tracker.track(TrackEvent(
        metric="test",
        quantity=1,
        license_id="lic_1",
        attribution={"custom": "value"},
    ))

    time.sleep(0.2)
    tracker.shutdown()

    assert len(received_batches) == 1
    attr = received_batches[0]["events"][0]["attribution"]
    assert attr["service"] == "test-service"
    assert attr["custom"] == "value"


def test_tracker_disabled(httpx_mock: HTTPXMock):
    """Test disabled tracker doesn't send events."""
    called = False

    def capture_request(request):
        nonlocal called
        called = True
        return httpx_mock.Response(status_code=200)

    httpx_mock.add_callback(capture_request, url="https://test.doow.co/telemetry/events")

    tracker = Tracker("dk_test_key", TrackerOptions(
        endpoint="https://test.doow.co",
        enabled=False,
        flush_at=1,
    ))

    tracker.track(TrackEvent(metric="test", quantity=1, license_id="lic_1"))

    time.sleep(0.1)
    tracker.shutdown()

    assert not called


def test_tracker_context_manager(httpx_mock: HTTPXMock):
    """Test tracker as context manager."""
    httpx_mock.add_response(url="https://test.doow.co/telemetry/events", status_code=200)

    with Tracker("dk_test_key", TrackerOptions(
        endpoint="https://test.doow.co",
        flush_at=1,
    )) as tracker:
        tracker.track(TrackEvent(metric="test", quantity=1, license_id="lic_1"))
