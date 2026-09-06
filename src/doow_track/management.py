"""Management API client for Doow SDK."""

import os
from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar

import httpx

from .errors import APIError
from .types import (
    App,
    Contract,
    CreateAppInput,
    CreateContractInput,
    CreateMetricInput,
    Expense,
    License,
    Metric,
    PaginatedResponse,
    PaginationParams,
    UpdateAppInput,
    UpdateContractInput,
    UpdateLicenseInput,
    UpdateMetricInput,
)

SDK_VERSION = "0.1.0"
DEFAULT_ENDPOINT = "https://api.doow.co"
DEFAULT_TIMEOUT = 30.0

T = TypeVar("T")


class PaginatedResult(Generic[T]):
    """Paginated API result."""

    def __init__(self, data: list[T], next_cursor: Optional[str], has_more: bool):
        self.data = data
        self.next_cursor = next_cursor
        self.has_more = has_more


@dataclass
class ManagementOptions:
    """Configuration for Management client."""

    endpoint: str = DEFAULT_ENDPOINT
    timeout: float = DEFAULT_TIMEOUT
    debug: bool = False


class BaseResource:
    """Base class for API resources."""

    def __init__(self, client: "Management"):
        self._client = client

    def _log(self, message: str) -> None:
        if self._client._options.debug:
            print(f"[doow/management] {message}")


class AppsResource(BaseResource):
    """Apps API resource."""

    def list(self, params: Optional[PaginationParams] = None) -> PaginatedResult[App]:
        """List all apps."""
        params = params or PaginationParams()
        self._log("GET /sdk/apps")
        data = self._client._get("/sdk/apps", {"limit": params.limit, "cursor": params.cursor})
        apps = [App(**item) for item in data.get("data", [])]
        return PaginatedResult(apps, data.get("next_cursor"), data.get("has_more", False))

    def get(self, app_id: str) -> App:
        """Get an app by ID."""
        self._log(f"GET /sdk/apps/{app_id}")
        data = self._client._get(f"/sdk/apps/{app_id}")
        return App(**data)

    def create(self, input: CreateAppInput) -> App:
        """Create a new app."""
        self._log("POST /sdk/apps")
        data = self._client._post("/sdk/apps", input.model_dump(exclude_none=True))
        return App(**data)

    def update(self, app_id: str, input: UpdateAppInput) -> App:
        """Update an app."""
        self._log(f"PATCH /sdk/apps/{app_id}")
        data = self._client._patch(f"/sdk/apps/{app_id}", input.model_dump(exclude_none=True))
        return App(**data)

    def delete(self, app_id: str) -> None:
        """Delete an app."""
        self._log(f"DELETE /sdk/apps/{app_id}")
        self._client._delete(f"/sdk/apps/{app_id}")


class ContractsResource(BaseResource):
    """Contracts API resource."""

    def list(
        self, app_id: str, params: Optional[PaginationParams] = None
    ) -> PaginatedResult[Contract]:
        """List contracts for an app."""
        params = params or PaginationParams()
        self._log(f"GET /sdk/apps/{app_id}/contracts")
        data = self._client._get(
            f"/sdk/apps/{app_id}/contracts", {"limit": params.limit, "cursor": params.cursor}
        )
        contracts = [Contract(**item) for item in data.get("data", [])]
        return PaginatedResult(contracts, data.get("next_cursor"), data.get("has_more", False))

    def get(self, contract_id: str) -> Contract:
        """Get a contract by ID."""
        self._log(f"GET /sdk/contracts/{contract_id}")
        data = self._client._get(f"/sdk/contracts/{contract_id}")
        return Contract(**data)

    def create(self, app_id: str, input: CreateContractInput) -> Contract:
        """Create a new contract."""
        self._log(f"POST /sdk/apps/{app_id}/contracts")
        data = self._client._post(
            f"/sdk/apps/{app_id}/contracts", input.model_dump(exclude_none=True)
        )
        return Contract(**data)

    def update(self, contract_id: str, input: UpdateContractInput) -> Contract:
        """Update a contract."""
        self._log(f"PATCH /sdk/contracts/{contract_id}")
        data = self._client._patch(
            f"/sdk/contracts/{contract_id}", input.model_dump(exclude_none=True)
        )
        return Contract(**data)

    def delete(self, contract_id: str) -> None:
        """Delete a contract."""
        self._log(f"DELETE /sdk/contracts/{contract_id}")
        self._client._delete(f"/sdk/contracts/{contract_id}")


class LicensesResource(BaseResource):
    """Licenses API resource."""

    def list(
        self, contract_id: str, params: Optional[PaginationParams] = None
    ) -> PaginatedResult[License]:
        """List licenses for a contract."""
        params = params or PaginationParams()
        self._log(f"GET /sdk/contracts/{contract_id}/licenses")
        data = self._client._get(
            f"/sdk/contracts/{contract_id}/licenses",
            {"limit": params.limit, "cursor": params.cursor},
        )
        licenses = [License(**item) for item in data.get("data", [])]
        return PaginatedResult(licenses, data.get("next_cursor"), data.get("has_more", False))

    def get(self, license_id: str) -> License:
        """Get a license by ID."""
        self._log(f"GET /sdk/licenses/{license_id}")
        data = self._client._get(f"/sdk/licenses/{license_id}")
        return License(**data)

    def update(self, license_id: str, input: UpdateLicenseInput) -> License:
        """Update a license."""
        self._log(f"PATCH /sdk/licenses/{license_id}")
        data = self._client._patch(
            f"/sdk/licenses/{license_id}", input.model_dump(exclude_none=True)
        )
        return License(**data)

    def delete(self, license_id: str) -> None:
        """Delete a license."""
        self._log(f"DELETE /sdk/licenses/{license_id}")
        self._client._delete(f"/sdk/licenses/{license_id}")


class MetricsResource(BaseResource):
    """Metrics API resource."""

    def list(
        self, license_id: str, params: Optional[PaginationParams] = None
    ) -> PaginatedResult[Metric]:
        """List metrics for a license."""
        params = params or PaginationParams()
        self._log(f"GET /sdk/licenses/{license_id}/metrics")
        data = self._client._get(
            f"/sdk/licenses/{license_id}/metrics",
            {"limit": params.limit, "cursor": params.cursor},
        )
        metrics = [Metric(**item) for item in data.get("data", [])]
        return PaginatedResult(metrics, data.get("next_cursor"), data.get("has_more", False))

    def get(self, metric_id: str) -> Metric:
        """Get a metric by ID."""
        self._log(f"GET /sdk/metrics/{metric_id}")
        data = self._client._get(f"/sdk/metrics/{metric_id}")
        return Metric(**data)

    def create(self, license_id: str, input: CreateMetricInput) -> Metric:
        """Create a new metric."""
        self._log(f"POST /sdk/licenses/{license_id}/metrics")
        data = self._client._post(
            f"/sdk/licenses/{license_id}/metrics", input.model_dump(exclude_none=True)
        )
        return Metric(**data)

    def update(self, metric_id: str, input: UpdateMetricInput) -> Metric:
        """Update a metric."""
        self._log(f"PATCH /sdk/metrics/{metric_id}")
        data = self._client._patch(
            f"/sdk/metrics/{metric_id}", input.model_dump(exclude_none=True)
        )
        return Metric(**data)

    def delete(self, metric_id: str) -> None:
        """Delete a metric."""
        self._log(f"DELETE /sdk/metrics/{metric_id}")
        self._client._delete(f"/sdk/metrics/{metric_id}")


@dataclass
class ListExpensesParams:
    """Parameters for listing expenses."""

    limit: int = 25
    cursor: Optional[str] = None
    app_id: Optional[str] = None
    year: Optional[int] = None
    month: Optional[int] = None


class ExpensesResource(BaseResource):
    """Expenses API resource."""

    def list(self, params: Optional[ListExpensesParams] = None) -> PaginatedResult[Expense]:
        """List expenses."""
        params = params or ListExpensesParams()
        self._log("GET /sdk/expenses")
        query: dict[str, Any] = {"limit": params.limit}
        if params.cursor:
            query["cursor"] = params.cursor
        if params.app_id:
            query["app_id"] = params.app_id
        if params.year:
            query["year"] = params.year
        if params.month:
            query["month"] = params.month

        data = self._client._get("/sdk/expenses", query)
        expenses = [Expense(**item) for item in data.get("data", [])]
        return PaginatedResult(expenses, data.get("next_cursor"), data.get("has_more", False))

    def get(self, expense_id: str) -> Expense:
        """Get an expense by ID."""
        self._log(f"GET /sdk/expenses/{expense_id}")
        data = self._client._get(f"/sdk/expenses/{expense_id}")
        return Expense(**data)


class Management:
    """Management API client."""

    def __init__(self, api_key: str, options: Optional[ManagementOptions] = None):
        self._options = options or ManagementOptions()
        self._api_key = os.environ.get("DOOW_TRACK_API_KEY", api_key)

        if env_endpoint := os.environ.get("DOOW_TRACK_ENDPOINT"):
            self._options.endpoint = env_endpoint

        self._client = httpx.Client(timeout=self._options.timeout)

        # Resources
        self.apps = AppsResource(self)
        self.contracts = ContractsResource(self)
        self.licenses = LicensesResource(self)
        self.metrics = MetricsResource(self)
        self.expenses = ExpensesResource(self)

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> dict:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"doow-track-python/{SDK_VERSION}",
        }

        response = self._client.request(
            method,
            f"{self._options.endpoint}{path}",
            headers=headers,
            params=params,
            json=json,
        )

        if response.status_code >= 400:
            try:
                data = response.json()
                raise APIError(
                    status=response.status_code,
                    message=data.get("message", response.reason_phrase),
                    error_class=data.get("errorClass"),
                    details=data,
                )
            except ValueError:
                raise APIError(
                    status=response.status_code,
                    message=response.reason_phrase,
                )

        if response.status_code == 204:
            return {}
        return response.json()

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        return self._request("GET", path, params=params)

    def _post(self, path: str, json: dict) -> dict:
        return self._request("POST", path, json=json)

    def _patch(self, path: str, json: dict) -> dict:
        return self._request("PATCH", path, json=json)

    def _delete(self, path: str) -> dict:
        return self._request("DELETE", path)

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> "Management":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class AsyncManagement:
    """Async Management API client."""

    def __init__(self, api_key: str, options: Optional[ManagementOptions] = None):
        self._options = options or ManagementOptions()
        self._api_key = os.environ.get("DOOW_TRACK_API_KEY", api_key)

        if env_endpoint := os.environ.get("DOOW_TRACK_ENDPOINT"):
            self._options.endpoint = env_endpoint

        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._options.timeout)
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> dict:
        client = await self._ensure_client()
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"doow-track-python/{SDK_VERSION}",
        }

        response = await client.request(
            method,
            f"{self._options.endpoint}{path}",
            headers=headers,
            params=params,
            json=json,
        )

        if response.status_code >= 400:
            try:
                data = response.json()
                raise APIError(
                    status=response.status_code,
                    message=data.get("message", response.reason_phrase),
                    error_class=data.get("errorClass"),
                    details=data,
                )
            except ValueError:
                raise APIError(
                    status=response.status_code,
                    message=response.reason_phrase,
                )

        if response.status_code == 204:
            return {}
        return response.json()

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()

    async def __aenter__(self) -> "AsyncManagement":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
