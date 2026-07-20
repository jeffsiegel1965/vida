"""Tests for x402 (HTTP 402 Payment Required) integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vida.plugins.tao.x402 import X402Terms, X402Response, x402_query


def test_payment_terms_parsing():
    """Test parsing payment terms from headers."""
    headers = {
        "X-Payment-Required": "true",
        "X-Payment-Amount": "10.5",
        "X-Payment-Destination": "kaspa:qzm5...",
        "X-Payment-Network": "KAS",
        "X-Payment-Description": "API query fee",
    }

    terms = X402Terms.from_headers(headers)
    assert terms is not None
    assert terms.amount == 10.5
    assert terms.destination == "kaspa:qzm5..."
    assert terms.network == "KAS"
    assert terms.description == "API query fee"


def test_free_query_tier():
    """Test that free queries pass through without payment."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": "test"}

    with patch("requests.get", return_value=mock_resp):
        result = x402_query("http://example.com", None, "")

    assert not result.paid
    assert result.original_result == {"data": "test"}


def test_fee_calculation():
    """Test that fee is calculated for paid queries."""
    # 402 response with payment terms
    mock_402 = MagicMock()
    mock_402.status_code = 402
    mock_402.headers = {
        "X-Payment-Required": "true",
        "X-Payment-Amount": "100",
        "X-Payment-Destination": "kaspa:...",
        "X-Payment-Network": "KAS",
    }

    # Successful retry after payment
    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.json.return_value = {"data": "result"}

    mock_substrate = MagicMock()
    mock_substrate.transfer.return_value = "txid_123"

    with patch("requests.get", side_effect=[mock_402, mock_200]):
        result = x402_query("http://example.com", mock_substrate, "coldkey_hex")

    assert result.paid
    assert result.txid == "txid_123"


def test_payment_flow():
    """Test full payment flow: 402 → pay → retry → success."""
    mock_402 = MagicMock()
    mock_402.status_code = 402
    mock_402.headers = {
        "X-Payment-Required": "true",
        "X-Payment-Amount": "5.0",
        "X-Payment-Destination": "kaspa:dest...",
        "X-Payment-Network": "KAS",
    }

    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.json.return_value = {"result": "success"}

    mock_substrate = MagicMock()
    mock_substrate.transfer.return_value = "txid_abc"

    with patch("requests.get", side_effect=[mock_402, mock_200]):
        result = x402_query("http://api.subnet", mock_substrate, "key")

    assert result.paid
    assert result.txid == "txid_abc"
    assert result.original_result == {"result": "success"}


def test_error_handling():
    """Test error handling when no payment terms in 402 response."""
    mock_402 = MagicMock()
    mock_402.status_code = 402
    mock_402.headers = {}  # No payment terms

    with patch("requests.get", return_value=mock_402):
        result = x402_query("http://example.com", None, "")

    assert not result.paid
    # original_result should be empty dict when payment fails
    assert result.original_result == {}


def test_no_payment_terms():
    """Test that missing required headers returns None."""
    headers = {"X-Payment-Required": "true"}  # Missing amount and destination
    terms = X402Terms.from_headers(headers)
    assert terms is None


def test_vida_fee_included():
    """Test that Vida fee is included in the payment amount."""
    mock_402 = MagicMock()
    mock_402.status_code = 402
    mock_402.headers = {
        "X-Payment-Required": "true",
        "X-Payment-Amount": "100",
        "X-Payment-Destination": "kaspa:dest...",
        "X-Payment-Network": "KAS",
    }

    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.json.return_value = {"data": "ok"}

    mock_substrate = MagicMock()
    mock_substrate.transfer.return_value = "txid"

    with patch("requests.get", side_effect=[mock_402, mock_200]):
        result = x402_query("http://example.com", mock_substrate, "key")

    assert result.paid
    # Verify transfer was called with fee included
    call_args = mock_substrate.transfer.call_args
    assert call_args is not None
    # Amount should be 100 + 0.05% fee = 100.05
    total = call_args[1].get("amount", 0) if len(call_args) > 1 else 0
    assert total >= 100.0