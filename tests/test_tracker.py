"""Tests for Tracker."""

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from doow_track import Tracker, TrackerOptions, TrackEvent, SerializedEvent


def test_tracker_track_queues_events():
    """Test tracking events adds them to buffer."""
    tracker = Tracker("dk_test_key", TrackerOptions(
        endpoint="https://test.doow.co",
        flush_at=100,  # High so we don't auto-flush
        flush_interval=1000.0,
        enabled=True,
    ))

    tracker.track(TrackEvent(metric="api_calls", quantity=1, license_id="lic_123"))
    tracker.track(TrackEvent(metric="api_calls", quantity=2, license_id="lic_123"))

    assert len(tracker._buffer) == 2
    assert tracker._buffer[0].metric == "api_calls"
    assert tracker._buffer[0].quantity == 1
    assert tracker._buffer[1].quantity == 2

    tracker._shutdown.set()


def test_tracker_before_send_drops_events():
    """Test before_send hook can drop events."""
    def before_send(event: SerializedEvent):
        if event.quantity == 0:
            return None
        return event

    tracker = Tracker("dk_test_key", TrackerOptions(
        endpoint="https://test.doow.co",
        flush_at=100,
        flush_interval=1000.0,
        before_send=before_send,
    ))

    tracker.track(TrackEvent(metric="test", quantity=0, license_id="lic_1"))
    tracker.track(TrackEvent(metric="test", quantity=5, license_id="lic_1"))

    assert len(tracker._buffer) == 1
    assert tracker._buffer[0].quantity == 5

    tracker._shutdown.set()


def test_tracker_before_send_modifies_events():
    """Test before_send hook can modify events."""
    def before_send(event: SerializedEvent):
        event.quantity *= 2
        return event

    tracker = Tracker("dk_test_key", TrackerOptions(
        endpoint="https://test.doow.co",
        flush_at=100,
        flush_interval=1000.0,
        before_send=before_send,
    ))

    tracker.track(TrackEvent(metric="test", quantity=5, license_id="lic_1"))

    assert len(tracker._buffer) == 1
    assert tracker._buffer[0].quantity == 10

    tracker._shutdown.set()


def test_tracker_attribution_merged():
    """Test SDK-level attribution is merged with event attribution."""
    tracker = Tracker("dk_test_key", TrackerOptions(
        endpoint="https://test.doow.co",
        flush_at=100,
        flush_interval=1000.0,
        attribution={"service": "test-service", "version": "1.0.0"},
    ))

    tracker.track(TrackEvent(
        metric="test",
        quantity=1,
        license_id="lic_1",
        attribution={"custom": "value"},
    ))

    assert len(tracker._buffer) == 1
    attr = tracker._buffer[0].attribution
    assert attr["service"] == "test-service"
    assert attr["version"] == "1.0.0"
    assert attr["custom"] == "value"

    tracker._shutdown.set()


def test_tracker_disabled_no_events():
    """Test disabled tracker doesn't queue events."""
    tracker = Tracker("dk_test_key", TrackerOptions(
        endpoint="https://test.doow.co",
        enabled=False,
        flush_at=1,
    ))

    tracker.track(TrackEvent(metric="test", quantity=1, license_id="lic_1"))

    assert len(tracker._buffer) == 0

    tracker._shutdown.set()


def test_tracker_context_manager():
    """Test tracker as context manager."""
    with Tracker("dk_test_key", TrackerOptions(
        endpoint="https://test.doow.co",
        flush_at=100,
        flush_interval=1000.0,
    )) as tracker:
        tracker.track(TrackEvent(metric="test", quantity=1, license_id="lic_1"))
        assert len(tracker._buffer) == 1


def test_tracker_event_serialization():
    """Test events are properly serialized."""
    tracker = Tracker("dk_test_key", TrackerOptions(
        endpoint="https://test.doow.co",
        flush_at=100,
        flush_interval=1000.0,
    ))

    tracker.track(TrackEvent(
        metric="api_calls",
        quantity=42,
        license_id="lic_123",
        unit="requests",
        metadata={"key": "value"},
    ))

    event = tracker._buffer[0]
    assert event.event_id is not None
    assert len(event.event_id) == 36  # UUID format
    assert event.timestamp is not None
    assert event.metric == "api_calls"
    assert event.quantity == 42
    assert event.license_id == "lic_123"
    assert event.unit == "requests"
    assert event.metadata == {"key": "value"}

    tracker._shutdown.set()


def test_tracker_queue_overflow():
    """Test queue drops oldest event when full."""
    tracker = Tracker("dk_test_key", TrackerOptions(
        endpoint="https://test.doow.co",
        flush_at=100,
        flush_interval=1000.0,
        max_queue_size=3,
    ))

    for i in range(5):
        tracker.track(TrackEvent(metric="test", quantity=i, license_id="lic_1"))

    assert len(tracker._buffer) == 3
    # Oldest events (0, 1) should be dropped
    assert tracker._buffer[0].quantity == 2
    assert tracker._buffer[1].quantity == 3
    assert tracker._buffer[2].quantity == 4

    tracker._shutdown.set()
