"""
Built-in tools — Flight search and availability (demo).

All data is static / in-memory.  No external API calls.
"""

from __future__ import annotations

from typing import Any

# ── Static flight inventory ────────────────────────────────────

_FLIGHTS: list[dict[str, Any]] = [
    {
        "flight_no": "AA101",
        "airline": "Alpha Airways",
        "origin": "JFK",
        "destination": "LHR",
        "depart": "2026-05-10T22:00",
        "arrive": "2026-05-11T10:30",
        "price_usd": 720,
        "seats_available": 23,
        "cabin": "economy",
    },
    {
        "flight_no": "AA102",
        "airline": "Alpha Airways",
        "origin": "JFK",
        "destination": "LHR",
        "depart": "2026-05-10T23:30",
        "arrive": "2026-05-11T11:45",
        "price_usd": 1890,
        "seats_available": 4,
        "cabin": "business",
    },
    {
        "flight_no": "BT205",
        "airline": "Blue Tail",
        "origin": "JFK",
        "destination": "CDG",
        "depart": "2026-05-10T21:00",
        "arrive": "2026-05-11T10:15",
        "price_usd": 680,
        "seats_available": 47,
        "cabin": "economy",
    },
    {
        "flight_no": "SW314",
        "airline": "SkyWest",
        "origin": "LAX",
        "destination": "NRT",
        "depart": "2026-05-15T11:00",
        "arrive": "2026-05-16T15:30",
        "price_usd": 1240,
        "seats_available": 12,
        "cabin": "economy",
    },
    {
        "flight_no": "SW315",
        "airline": "SkyWest",
        "origin": "LAX",
        "destination": "NRT",
        "depart": "2026-05-15T13:30",
        "arrive": "2026-05-16T18:00",
        "price_usd": 2850,
        "seats_available": 6,
        "cabin": "business",
    },
    {
        "flight_no": "AA408",
        "airline": "Alpha Airways",
        "origin": "SFO",
        "destination": "FCO",
        "depart": "2026-05-20T19:00",
        "arrive": "2026-05-21T14:45",
        "price_usd": 890,
        "seats_available": 31,
        "cabin": "economy",
    },
]


def search_flights(
    origin: str = "",
    destination: str = "",
    cabin: str = "",
    max_price_usd: float = 0,
    **kwargs: Any,
) -> dict[str, Any]:
    """Search available flights by origin, destination, cabin, and price cap.

    Parameters
    ----------
    origin : str
        Origin airport code (e.g. "JFK").  Case-insensitive.
    destination : str
        Destination airport code (e.g. "LHR").  Case-insensitive.
    cabin : str
        Optional cabin filter: "economy" or "business".
    max_price_usd : float
        Optional maximum price in USD.  0 = no limit.
    """
    origin_u = (origin or "").strip().upper()
    dest_u = (destination or "").strip().upper()
    cabin_l = (cabin or "").strip().lower()

    matches = []
    for flight in _FLIGHTS:
        if origin_u and flight["origin"] != origin_u:
            continue
        if dest_u and flight["destination"] != dest_u:
            continue
        if cabin_l and flight["cabin"] != cabin_l:
            continue
        if max_price_usd > 0 and flight["price_usd"] > max_price_usd:
            continue
        matches.append(flight)

    matches.sort(key=lambda f: f["price_usd"])

    return {
        "query": {
            "origin": origin_u,
            "destination": dest_u,
            "cabin": cabin_l or "any",
            "max_price_usd": max_price_usd or None,
        },
        "count": len(matches),
        "flights": matches,
    }


def get_flight_details(flight_no: str = "", **kwargs: Any) -> dict[str, Any]:
    """Look up a specific flight by its flight number."""
    fn = (flight_no or "").strip().upper()
    for flight in _FLIGHTS:
        if flight["flight_no"] == fn:
            return {**flight}
    return {
        "error": f"Flight '{fn}' not found",
        "available_flights": [f["flight_no"] for f in _FLIGHTS],
    }
