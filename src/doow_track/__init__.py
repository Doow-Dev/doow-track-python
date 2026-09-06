"""Doow SDK for Python - usage telemetry and management."""

from .errors import APIError, ConfigurationError, DoowError, ValidationError
from .management import (
    AsyncManagement,
    ListExpensesParams,
    Management,
    ManagementOptions,
    PaginatedResult,
)
from .tracker import (
    AsyncTracker,
    FileOfflineStore,
    OfflineStore,
    Tracker,
    TrackerOptions,
)
from .types import (
    App,
    CarryoverPolicy,
    Contract,
    ContractType,
    CreateAppInput,
    CreateContractInput,
    CreateMetricInput,
    EntitlementPeriod,
    EventKind,
    Expense,
    License,
    LicenseInput,
    LicenseType,
    Metric,
    PaginatedResponse,
    PaginationParams,
    RateKind,
    RateLimit,
    SerializedEvent,
    TrackEvent,
    UpdateAppInput,
    UpdateContractInput,
    UpdateLicenseInput,
    UpdateMetricInput,
    UsageAggregationType,
)

__version__ = "0.1.0"

__all__ = [
    # Version
    "__version__",
    # Tracker
    "Tracker",
    "AsyncTracker",
    "TrackerOptions",
    "TrackEvent",
    "SerializedEvent",
    "EventKind",
    "OfflineStore",
    "FileOfflineStore",
    # Management
    "Management",
    "AsyncManagement",
    "ManagementOptions",
    "PaginatedResult",
    "PaginationParams",
    "PaginatedResponse",
    "ListExpensesParams",
    # Resources
    "App",
    "CreateAppInput",
    "UpdateAppInput",
    "Contract",
    "CreateContractInput",
    "UpdateContractInput",
    "ContractType",
    "License",
    "LicenseInput",
    "UpdateLicenseInput",
    "LicenseType",
    "Metric",
    "CreateMetricInput",
    "UpdateMetricInput",
    "UsageAggregationType",
    "RateKind",
    "EntitlementPeriod",
    "CarryoverPolicy",
    "Expense",
    "RateLimit",
    # Errors
    "DoowError",
    "APIError",
    "ValidationError",
    "ConfigurationError",
]
