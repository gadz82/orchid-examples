"""
Built-in tools — Bookings (flights, hotels).

These tools are flagged with ``requires_approval: true`` in ``agents.yaml``
to trigger Enhancement #7 (Human-in-the-Loop).  The graph will pause at
``interrupt()`` before calling them, giving the user a chance to approve
or deny the booking.

All data is static / in-memory.  No external API calls.
"""

from __future__ import annotations

import uuid
from typing import Any

# ── In-memory booking store ─────────────────────────────────────

_BOOKINGS: dict[str, dict[str, Any]] = {}


def book_flight(
    flight_no: str = "",
    passenger_name: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    """Book a flight for a passenger. Triggers HITL approval.

    Parameters
    ----------
    flight_no : str
        Flight number from ``search_flights`` (e.g. "AA101").
    passenger_name : str
        Full name of the passenger.
    """
    fn = (flight_no or "").strip().upper()
    name = (passenger_name or "").strip()

    if not fn:
        return {"error": "Missing flight_no"}
    if not name:
        return {"error": "Missing passenger_name"}

    # Validate flight exists
    from .flights import get_flight_details

    flight = get_flight_details(fn)
    if "error" in flight:
        return flight

    booking_id = f"BKF-{uuid.uuid4().hex[:8].upper()}"
    record = {
        "booking_id": booking_id,
        "type": "flight",
        "flight_no": fn,
        "passenger_name": name,
        "status": "confirmed",
        "airline": flight["airline"],
        "origin": flight["origin"],
        "destination": flight["destination"],
        "depart": flight["depart"],
        "arrive": flight["arrive"],
        "cabin": flight["cabin"],
        "price_usd": flight["price_usd"],
    }
    _BOOKINGS[booking_id] = record
    return record


def book_hotel(
    hotel_id: str = "",
    guest_name: str = "",
    check_in: str = "",
    check_out: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    """Book a hotel room. Triggers HITL approval.

    Parameters
    ----------
    hotel_id : str
        Hotel ID from ``search_hotels`` (e.g. "HTL-LON-001").
    guest_name : str
        Full name of the primary guest.
    check_in : str
        Check-in date (YYYY-MM-DD).
    check_out : str
        Check-out date (YYYY-MM-DD).
    """
    hid = (hotel_id or "").strip().upper()
    name = (guest_name or "").strip()

    if not hid or not name or not check_in or not check_out:
        missing = [
            k for k, v in [
                ("hotel_id", hid),
                ("guest_name", name),
                ("check_in", check_in),
                ("check_out", check_out),
            ] if not v
        ]
        return {"error": f"Missing required fields: {missing}"}

    from .hotels import get_hotel_details

    hotel = get_hotel_details(hid)
    if "error" in hotel:
        return hotel

    # Naive night count: assume YYYY-MM-DD strings, not worth parsing here.
    try:
        from datetime import date

        nights = (date.fromisoformat(check_out) - date.fromisoformat(check_in)).days
    except ValueError:
        return {"error": "check_in / check_out must be YYYY-MM-DD"}

    if nights <= 0:
        return {"error": "check_out must be after check_in"}

    booking_id = f"BKH-{uuid.uuid4().hex[:8].upper()}"
    total = nights * hotel["nightly_usd"]
    record = {
        "booking_id": booking_id,
        "type": "hotel",
        "hotel_id": hid,
        "hotel_name": hotel["name"],
        "city": hotel["city"],
        "guest_name": name,
        "check_in": check_in,
        "check_out": check_out,
        "nights": nights,
        "nightly_usd": hotel["nightly_usd"],
        "total_usd": total,
        "status": "confirmed",
    }
    _BOOKINGS[booking_id] = record
    return record


def cancel_booking(booking_id: str = "", **kwargs: Any) -> dict[str, Any]:
    """Cancel a confirmed booking. Triggers HITL approval."""
    bid = (booking_id or "").strip().upper()
    if bid not in _BOOKINGS:
        return {"error": f"Booking '{bid}' not found"}
    record = _BOOKINGS[bid]
    if record["status"] == "cancelled":
        return {"error": "Already cancelled", "booking": record}
    record["status"] = "cancelled"
    return record


def list_bookings(**kwargs: Any) -> dict[str, Any]:
    """List all bookings in the current session (in-memory only)."""
    return {"count": len(_BOOKINGS), "bookings": list(_BOOKINGS.values())}
