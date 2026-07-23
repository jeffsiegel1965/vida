from typing import Dict, Optional

import requests
from requests.exceptions import RequestException

from ..covenant.fees import calc_subnet_query_fee


class X402Terms:
    """Payment terms from a 402 response."""

    def __init__(
        self,
        amount: float,
        destination: str,
        network: str,
        description: str = "",
        expires_at: Optional[int] = None,
        challenge_expires_at: Optional[int] = None,
    ):
        self.amount = amount
        self.destination = destination
        self.network = network
        self.description = description
        self.expires_at = expires_at
        self.challenge_expires_at = challenge_expires_at

    @classmethod
    def from_headers(cls, headers: Dict[str, str]) -> Optional["X402Terms"]:
        """Parse payment terms from HTTP headers."""
        if not all(key in headers for key in ["X-Payment-Required", "X-Payment-Amount", "X-Payment-Destination"]):
            return None

        # Enforce expiry ordering: authorization.expiresAt ≤ challengeExpiresAt
        expires_at = int(headers.get("X-Payment-Expires-At", "0")) if headers.get("X-Payment-Expires-At") else None
        challenge_expires_at = (
            int(headers.get("X-Challenge-Expires-At", "0")) if headers.get("X-Challenge-Expires-At") else None
        )

        if expires_at and challenge_expires_at and expires_at > challenge_expires_at:
            raise ValueError("Authorization expiry must not exceed challenge expiry")

        return cls(
            amount=float(headers["X-Payment-Amount"]),
            destination=headers["X-Payment-Destination"],
            network=headers.get("X-Payment-Network", "KAS"),
            description=headers.get("X-Payment-Description", ""),
            expires_at=expires_at,
            challenge_expires_at=challenge_expires_at,
        )


class X402Response:
    """Result of a paid 402 request."""

    def __init__(self, paid: bool, txid: str = "", original_result: Optional[dict] = None):
        self.paid = paid
        self.txid = txid
        self.original_result = original_result or {}


def x402_pay(substrate_client, coldkey_hex: str, terms: X402Terms) -> str:
    """
    Pay the required amount via substrate transfer.
    Returns the transaction ID.
    """
    # No Vida fees — wallet is free.
    total_amount = terms.amount

    # Execute substrate transfer
    return substrate_client.transfer(
        dest=terms.destination, amount=total_amount, coldkey=coldkey_hex, memo=f"X402: {terms.description}"
    )


def x402_query(
    url: str, substrate_client, coldkey_hex: str, method: str = "GET", body: Optional[dict] = None, max_retries: int = 5
) -> X402Response:
    """
    Query an endpoint with automatic 402 payment handling.

    1. Sends the initial request
    2. If 402, parses payment terms
    3. Pays via substrate transfer
    4. Retries with payment proof
    5. Returns the result
    """
    try:
        # Initial request
        if method.upper() == "GET":
            resp = requests.get(url)
        else:
            resp = requests.post(url, json=body)

        # Handle 402 response
        if resp.status_code == 402:
            terms = X402Terms.from_headers(resp.headers)
            if not terms:
                return X402Response(paid=False)

            # Pay and retry with proof
            txid = x402_pay(substrate_client, coldkey_hex, terms)

            # Retry with payment proof
            headers = {"X-Payment-Proof": txid}
            if method.upper() == "GET":
                resp = requests.get(url, headers=headers)
            else:
                resp = requests.post(url, json=body, headers=headers)

            return X402Response(paid=True, txid=txid, original_result=resp.json() if resp.status_code == 200 else None)

        # Successful non-402 response
        return X402Response(paid=False, original_result=resp.json() if resp.status_code == 200 else None)
    except RequestException:
        # Retry on network errors (up to max_retries)
        if max_retries > 0:
            return x402_query(url, substrate_client, coldkey_hex, method, body, max_retries - 1)

        return X402Response(paid=False)
