"""Tests for Management API."""

import pytest
from pytest_httpx import HTTPXMock

from doow_track import (
    Management,
    ManagementOptions,
    CreateAppInput,
    CreateContractInput,
    CreateMetricInput,
    LicenseInput,
    ContractType,
    LicenseType,
    APIError,
)


def test_apps_list(httpx_mock: HTTPXMock):
    """Test listing apps."""
    httpx_mock.add_response(
        url="https://test.doow.co/sdk/apps?limit=25",
        json={
            "data": [
                {
                    "id": "app_1",
                    "name": "Test App",
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            ],
            "has_more": False,
        },
    )

    with Management("dk_test_key", ManagementOptions(endpoint="https://test.doow.co")) as mgmt:
        result = mgmt.apps.list()

    assert len(result.data) == 1
    assert result.data[0].name == "Test App"
    assert result.has_more is False


def test_apps_create(httpx_mock: HTTPXMock):
    """Test creating an app."""
    httpx_mock.add_response(
        url="https://test.doow.co/sdk/apps",
        method="POST",
        json={
            "id": "app_new",
            "name": "New App",
            "description": "Test description",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        },
    )

    with Management("dk_test_key", ManagementOptions(endpoint="https://test.doow.co")) as mgmt:
        app = mgmt.apps.create(CreateAppInput(name="New App", description="Test description"))

    assert app.id == "app_new"
    assert app.name == "New App"


def test_contracts_create(httpx_mock: HTTPXMock):
    """Test creating a contract with licenses."""
    httpx_mock.add_response(
        url="https://test.doow.co/sdk/apps/app_1/contracts",
        method="POST",
        json={
            "id": "contract_1",
            "title": "Enterprise",
            "contract_type": "PAY_AS_YOU_GO",
            "app_id": "app_1",
            "licenses": [
                {
                    "id": "lic_1",
                    "name": "API Usage",
                    "license_type": "USAGE_BASED",
                    "contract_id": "contract_1",
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": "2026-01-01T00:00:00Z",
                }
            ],
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        },
    )

    with Management("dk_test_key", ManagementOptions(endpoint="https://test.doow.co")) as mgmt:
        contract = mgmt.contracts.create("app_1", CreateContractInput(
            title="Enterprise",
            contract_type=ContractType.PAY_AS_YOU_GO,
            licenses=[LicenseInput(name="API Usage", license_type=LicenseType.USAGE_BASED)],
        ))

    assert contract.id == "contract_1"
    assert len(contract.licenses) == 1
    assert contract.licenses[0].name == "API Usage"


def test_metrics_create(httpx_mock: HTTPXMock):
    """Test creating a metric."""
    httpx_mock.add_response(
        url="https://test.doow.co/sdk/licenses/lic_1/metrics",
        method="POST",
        json={
            "id": "metric_1",
            "metric_type": "api_calls",
            "usage_aggregation_type": "CUMULATIVE",
            "rate_kind": "PER_UNIT",
            "license_id": "lic_1",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        },
    )

    with Management("dk_test_key", ManagementOptions(endpoint="https://test.doow.co")) as mgmt:
        metric = mgmt.metrics.create("lic_1", CreateMetricInput(metric_type="api_calls"))

    assert metric.id == "metric_1"
    assert metric.metric_type == "api_calls"


def test_api_error_handling(httpx_mock: HTTPXMock):
    """Test API error handling."""
    httpx_mock.add_response(
        url="https://test.doow.co/sdk/apps/invalid",
        status_code=404,
        json={"message": "App not found", "errorClass": "NOT_FOUND"},
    )

    with Management("dk_test_key", ManagementOptions(endpoint="https://test.doow.co")) as mgmt:
        with pytest.raises(APIError) as exc_info:
            mgmt.apps.get("invalid")

    assert exc_info.value.status == 404
    assert exc_info.value.is_not_found()


def test_expenses_list(httpx_mock: HTTPXMock):
    """Test listing expenses."""
    httpx_mock.add_response(
        url="https://test.doow.co/sdk/expenses?limit=25&year=2026",
        json={
            "data": [
                {
                    "id": "exp_1",
                    "app_id": "app_1",
                    "month": 9,
                    "year": 2026,
                    "total": 150.00,
                    "currency": "USD",
                    "created_at": "2026-09-01T00:00:00Z",
                    "updated_at": "2026-09-01T00:00:00Z",
                }
            ],
            "has_more": False,
        },
    )

    from doow_track import ListExpensesParams

    with Management("dk_test_key", ManagementOptions(endpoint="https://test.doow.co")) as mgmt:
        result = mgmt.expenses.list(ListExpensesParams(year=2026))

    assert len(result.data) == 1
    assert result.data[0].total == 150.00
