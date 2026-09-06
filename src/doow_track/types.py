"""Type definitions for Doow SDK."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EventKind(str, Enum):
    USAGE = "USAGE"
    ADJUSTMENT = "ADJUSTMENT"


class ContractType(str, Enum):
    SUBSCRIPTION = "SUBSCRIPTION"
    PAY_AS_YOU_GO = "PAY_AS_YOU_GO"
    HYBRID = "HYBRID"
    TRIAL = "TRIAL"
    FREEMIUM = "FREEMIUM"


class LicenseType(str, Enum):
    SEAT_BASED = "SEAT_BASED"
    USAGE_BASED = "USAGE_BASED"
    FEATURE_FLAG = "FEATURE_FLAG"
    HYBRID = "HYBRID"


class UsageAggregationType(str, Enum):
    SUM = "SUM"
    MAX = "MAX"
    CUMULATIVE = "CUMULATIVE"


class RateKind(str, Enum):
    PER_UNIT = "PER_UNIT"
    FLAT_FEE = "FLAT_FEE"
    PER_SEAT = "PER_SEAT"
    TIERED = "TIERED"
    VOLUME = "VOLUME"


class EntitlementPeriod(str, Enum):
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"
    QUARTERLY = "QUARTERLY"
    WEEKLY = "WEEKLY"
    DAILY = "DAILY"
    ONE_TIME = "ONE_TIME"


class CarryoverPolicy(str, Enum):
    NO_CARRYOVER = "NO_CARRYOVER"
    FULL_CARRYOVER = "FULL_CARRYOVER"
    CAPPED_CARRYOVER = "CAPPED_CARRYOVER"


# --- Track Event Types ---


class TrackEvent(BaseModel):
    """Event to track usage."""

    metric: str
    quantity: float
    license_id: str
    unit: Optional[str] = None
    kind: EventKind = EventKind.USAGE
    timestamp: Optional[datetime] = None
    source_system: Optional[str] = None
    metric_tuple_hint: Optional[str] = None
    attribution: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None


class SerializedEvent(TrackEvent):
    """Event with generated fields."""

    event_id: str
    timestamp: str  # type: ignore[assignment]


# --- Management API Types ---


class App(BaseModel):
    """Application resource."""

    id: str
    name: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    vendor_app_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class CreateAppInput(BaseModel):
    """Input for creating an app."""

    name: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    vendor_app_id: Optional[str] = None


class UpdateAppInput(BaseModel):
    """Input for updating an app."""

    name: Optional[str] = None
    description: Optional[str] = None
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    vendor_app_id: Optional[str] = None


class License(BaseModel):
    """License resource."""

    id: str
    name: str
    license_type: LicenseType
    contract_id: str
    created_at: datetime
    updated_at: datetime


class LicenseInput(BaseModel):
    """Input for creating a license within a contract."""

    name: str
    license_type: LicenseType = LicenseType.USAGE_BASED


class UpdateLicenseInput(BaseModel):
    """Input for updating a license."""

    name: Optional[str] = None
    license_type: Optional[LicenseType] = None


class Contract(BaseModel):
    """Contract resource."""

    id: str
    title: str
    contract_type: ContractType
    app_id: str
    licenses: list[License] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CreateContractInput(BaseModel):
    """Input for creating a contract."""

    title: str
    contract_type: ContractType = ContractType.PAY_AS_YOU_GO
    licenses: list[LicenseInput] = Field(default_factory=list)


class UpdateContractInput(BaseModel):
    """Input for updating a contract."""

    title: Optional[str] = None
    contract_type: Optional[ContractType] = None


class Metric(BaseModel):
    """Metric resource."""

    id: str
    metric_type: str
    usage_aggregation_type: UsageAggregationType = UsageAggregationType.CUMULATIVE
    rate_kind: RateKind = RateKind.PER_UNIT
    usage_rate: Optional[float] = None
    license_id: str
    created_at: datetime
    updated_at: datetime


class CreateMetricInput(BaseModel):
    """Input for creating a metric."""

    metric_type: str
    usage_aggregation_type: Optional[UsageAggregationType] = None
    rate_kind: Optional[RateKind] = None
    usage_rate: Optional[float] = None


class UpdateMetricInput(BaseModel):
    """Input for updating a metric."""

    metric_type: Optional[str] = None
    usage_aggregation_type: Optional[UsageAggregationType] = None
    rate_kind: Optional[RateKind] = None
    usage_rate: Optional[float] = None


class Expense(BaseModel):
    """Expense resource."""

    id: str
    app_id: str
    month: int
    year: int
    total: float
    currency: str = "USD"
    created_at: datetime
    updated_at: datetime


class PaginationParams(BaseModel):
    """Pagination parameters."""

    limit: int = 25
    cursor: Optional[str] = None


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""

    data: list[Any]
    next_cursor: Optional[str] = None
    has_more: bool = False


class RateLimit(BaseModel):
    """Rate limit info from API."""

    limit: int
    remaining: int
    reset: datetime
