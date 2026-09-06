# Doow Track Python SDK

[![PyPI](https://img.shields.io/pypi/v/doow-track?color=blue)](https://pypi.org/project/doow-track/)
[![Python](https://img.shields.io/pypi/pyversions/doow-track)](https://pypi.org/project/doow-track/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Official Python SDK for [Doow](https://doow.co) usage telemetry and management. Track SaaS usage, manage subscriptions, and monitor expenses.

## Features

| Feature | Description |
|---------|-------------|
| **Sync & Async** | Both synchronous and async APIs |
| **Batching** | Events queued and sent in configurable batches |
| **Compression** | Automatic gzip for payloads >1KB |
| **Retries** | Exponential backoff with configurable retry count |
| **Offline Storage** | Persist failed batches to disk |
| **Type Safety** | Full Pydantic models with type hints |
| **Hooks** | `before_send`, `before_flush`, `on_error` callbacks |

---

## Installation

```bash
pip install doow-track
```

---

## Quick Start

### Track Usage Events

```python
from doow_track import Tracker, TrackEvent

# Sync tracker
with Tracker("dk_your_api_key") as tracker:
    tracker.track(TrackEvent(
        metric="api_calls",
        quantity=1,
        license_id="lic_abc123",
    ))

    # Rich event with attribution
    tracker.track(TrackEvent(
        metric="tokens_generated",
        quantity=1500,
        unit="tokens",
        license_id="lic_abc123",
        attribution={"model": "gpt-4", "region": "us-east-1"},
        metadata={"request_id": "req_xyz"},
    ))
```

### Async Tracker

```python
import asyncio
from doow_track import AsyncTracker, TrackEvent

async def main():
    async with AsyncTracker("dk_your_api_key") as tracker:
        await tracker.track(TrackEvent(
            metric="api_calls",
            quantity=1,
            license_id="lic_abc123",
        ))

asyncio.run(main())
```

### Management API

```python
from doow_track import (
    Management,
    CreateAppInput,
    CreateContractInput,
    CreateMetricInput,
    LicenseInput,
    ContractType,
    LicenseType,
)

with Management("dk_your_api_key") as mgmt:
    # Create an app
    app = mgmt.apps.create(CreateAppInput(
        name="My SaaS Platform",
        description="Usage-based billing for API calls",
    ))
    print(f"Created app: {app.id}")

    # Create a contract with license
    contract = mgmt.contracts.create(app.id, CreateContractInput(
        title="Enterprise Plan",
        contract_type=ContractType.PAY_AS_YOU_GO,
        licenses=[
            LicenseInput(name="API Usage", license_type=LicenseType.USAGE_BASED),
        ],
    ))
    license_id = contract.licenses[0].id

    # Create a metric
    metric = mgmt.metrics.create(license_id, CreateMetricInput(
        metric_type="api_calls",
    ))
    print(f"Created metric: {metric.id}")
```

---

## Configuration

### Tracker Options

```python
from doow_track import Tracker, TrackerOptions, FileOfflineStore

tracker = Tracker("dk_your_api_key", TrackerOptions(
    # Connection
    endpoint="https://api.doow.co",
    timeout=10.0,

    # Batching
    flush_at=20,              # Flush after N events
    flush_interval=10.0,      # Flush every N seconds
    max_payload_bytes=450*1024,
    max_queue_size=10000,

    # Reliability
    retry_count=3,
    shutdown_timeout=5.0,
    disable_compression=False,

    # Persistence
    offline_store=FileOfflineStore(),

    # SDK-level attribution
    attribution={
        "service": "api-gateway",
        "version": "1.2.3",
    },

    # Hooks
    on_error=lambda e: print(f"Error: {e}"),
    before_send=lambda e: e if e.quantity > 0 else None,
    before_flush=lambda events: events,

    # Control
    enabled=True,
    debug=True,
))
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DOOW_TRACK_API_KEY` | API key (overrides constructor) | — |
| `DOOW_TRACK_ENDPOINT` | Custom API endpoint | `https://api.doow.co` |
| `DOOW_TRACK_DISABLED` | Set `true` to disable tracking | `false` |
| `DOOW_TRACK_DEBUG` | Set `true` for debug logs | `false` |
| `DOOW_TRACK_FLUSH_AT` | Events before flush | `20` |
| `DOOW_TRACK_FLUSH_INTERVAL` | Milliseconds between flushes | `10000` |

---

## Management API Reference

### Apps

```python
# List
apps = mgmt.apps.list()
for app in apps.data:
    print(app.name)

# Create
app = mgmt.apps.create(CreateAppInput(name="My App"))

# Get
app = mgmt.apps.get("app_id")

# Update
app = mgmt.apps.update("app_id", UpdateAppInput(name="New Name"))

# Delete
mgmt.apps.delete("app_id")
```

### Contracts

```python
# List contracts for an app
contracts = mgmt.contracts.list(app_id)

# Create with licenses
contract = mgmt.contracts.create(app_id, CreateContractInput(
    title="Pro Plan",
    contract_type=ContractType.SUBSCRIPTION,
    licenses=[
        LicenseInput(name="Seats", license_type=LicenseType.SEAT_BASED),
        LicenseInput(name="API", license_type=LicenseType.USAGE_BASED),
    ],
))

# Get / Update / Delete
contract = mgmt.contracts.get(contract_id)
contract = mgmt.contracts.update(contract_id, UpdateContractInput(...))
mgmt.contracts.delete(contract_id)
```

### Licenses

```python
# List licenses for a contract
licenses = mgmt.licenses.list(contract_id)

# Get / Update / Delete
license = mgmt.licenses.get(license_id)
license = mgmt.licenses.update(license_id, UpdateLicenseInput(...))
mgmt.licenses.delete(license_id)
```

### Metrics

```python
# List metrics for a license
metrics = mgmt.metrics.list(license_id)

# Create
metric = mgmt.metrics.create(license_id, CreateMetricInput(
    metric_type="api_calls",
))

# Get / Update / Delete
metric = mgmt.metrics.get(metric_id)
metric = mgmt.metrics.update(metric_id, UpdateMetricInput(...))
mgmt.metrics.delete(metric_id)
```

### Expenses

```python
from doow_track import ListExpensesParams

# List expenses
expenses = mgmt.expenses.list(ListExpensesParams(
    app_id=app_id,
    year=2026,
    month=9,
))

# Get single expense
expense = mgmt.expenses.get(expense_id)
```

---

## Error Handling

```python
from doow_track import APIError

try:
    app = mgmt.apps.get("invalid_id")
except APIError as e:
    if e.is_not_found():
        print("Resource not found")
    elif e.is_unauthorized():
        print("Invalid API key")
    elif e.is_forbidden():
        print("Missing required scope")
    elif e.is_rate_limited():
        print("Rate limited, retry later")
    else:
        print(f"API error {e.status}: {e.message}")
```

---

## Offline Storage

Persist failed batches to disk and automatically drain when connectivity returns:

```python
from doow_track import Tracker, TrackerOptions, FileOfflineStore

tracker = Tracker("dk_your_api_key", TrackerOptions(
    offline_store=FileOfflineStore(),  # defaults to ~/.doow/offline
))
```

---

## Framework Integration

### FastAPI

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from doow_track import AsyncTracker, TrackEvent

tracker: AsyncTracker

@asynccontextmanager
async def lifespan(app: FastAPI):
    global tracker
    tracker = AsyncTracker("dk_your_api_key")
    yield
    await tracker.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/api/generate")
async def generate():
    await tracker.track(TrackEvent(
        metric="api_calls",
        quantity=1,
        license_id="lic_abc123",
    ))
    return {"result": "ok"}
```

### Django

```python
# settings.py
DOOW_API_KEY = "dk_your_api_key"

# apps.py
from django.apps import AppConfig
from doow_track import Tracker

class MyAppConfig(AppConfig):
    name = "myapp"
    tracker = None

    def ready(self):
        from django.conf import settings
        MyAppConfig.tracker = Tracker(settings.DOOW_API_KEY)

# views.py
from doow_track import TrackEvent
from .apps import MyAppConfig

def my_view(request):
    MyAppConfig.tracker.track(TrackEvent(
        metric="page_views",
        quantity=1,
        license_id="lic_abc123",
    ))
```

---

## License

MIT
