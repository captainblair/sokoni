"""The tool contract: what an AI is allowed to know it can do."""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.agent.registry import UnknownTool, all_tools, get_tool

pytestmark = pytest.mark.django_db

URL = reverse("agent-tools")

EXPECTED_TOOLS = {
    "record_sale",
    "record_income",
    "record_purchase",
    "record_expense",
    "create_receivable",
    "create_payable",
    "record_debt_payment",
    "get_cash_position",
    "get_summary",
    "get_debts",
    "get_recent_transactions",
    "get_party_balance",
    "check_float_risk",
    "get_daily_brief",
}


def test_the_registry_holds_every_promised_tool():
    assert {tool.name for tool in all_tools()} == EXPECTED_TOOLS


def test_the_registry_is_published(authenticated_client):
    response = authenticated_client.get(URL)

    assert response.status_code == status.HTTP_200_OK
    assert {tool["name"] for tool in response.data["tools"]} == EXPECTED_TOOLS


def test_every_tool_describes_itself(authenticated_client):
    for tool in authenticated_client.get(URL).data["tools"]:
        assert tool["description"], f"{tool['name']} has no description"
        assert isinstance(tool["mutating"], bool)


def test_writes_are_marked_as_such(authenticated_client):
    tools = {tool["name"]: tool for tool in authenticated_client.get(URL).data["tools"]}

    assert tools["record_sale"]["mutating"] is True
    assert tools["get_cash_position"]["mutating"] is False


def test_parameters_carry_the_vocabulary(authenticated_client):
    tools = {tool["name"]: tool for tool in authenticated_client.get(URL).data["tools"]}
    params = {p["name"]: p for p in tools["record_sale"]["parameters"]}

    assert params["amount"]["type"] == "decimal"
    assert params["amount"]["required"] is False
    assert params["party"]["description"]
    assert "credit" in params["payment_status"]["choices"]


def test_the_registry_needs_authentication(api_client):
    assert api_client.get(URL).status_code == status.HTTP_401_UNAUTHORIZED


def test_an_unknown_tool_cannot_be_fetched():
    with pytest.raises(UnknownTool):
        get_tool("drop_database")
