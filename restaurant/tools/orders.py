"""
Built-in tools — order placement, status tracking, and bill calculation.

All data is static / in-memory.  No external API calls.
Functions accept ``**kwargs`` to absorb extra arguments
(``query``, ``context``) that GenericAgent passes automatically.
"""

from __future__ import annotations

import uuid
from typing import Any

# -- In-memory order store (mock) -------------------------------------------

_ORDERS: dict[str, dict[str, Any]] = {
    "ORD-001": {
        "order_id": "ORD-001",
        "table_number": 5,
        "items": [
            {"name": "Margherita Pizza", "qty": 1, "price": 14.99},
            {"name": "Classic Caesar Salad", "qty": 1, "price": 12.50},
            {"name": "Classic Tiramisu", "qty": 2, "price": 11.00},
        ],
        "status": "preparing",
        "estimated_time_min": 20,
        "special_requests": "No anchovies on the salad",
    },
    "ORD-002": {
        "order_id": "ORD-002",
        "table_number": 12,
        "items": [
            {"name": "Filet Mignon", "qty": 2, "price": 42.00},
            {"name": "Truffle Mushroom Risotto", "qty": 1, "price": 22.50},
        ],
        "status": "ready",
        "estimated_time_min": 0,
        "special_requests": "Medium-rare on both steaks",
    },
}

# -- Menu price lookup (simplified) -----------------------------------------

_PRICES: dict[str, float] = {
    "margherita pizza": 14.99,
    "truffle mushroom risotto": 22.50,
    "grilled atlantic salmon": 28.00,
    "classic caesar salad": 12.50,
    "vegan buddha bowl": 16.99,
    "filet mignon": 42.00,
    "classic tiramisu": 11.00,
    "spicy thai green curry": 18.50,
    "pan-seared duck breast": 34.00,
    "lobster linguine": 38.00,
}


def _find_price(item_name: str) -> float | None:
    """Case-insensitive price lookup with partial matching."""
    key = item_name.strip().lower()
    if key in _PRICES:
        return _PRICES[key]
    for name, price in _PRICES.items():
        if key in name or name in key:
            return price
    return None


# -- Public tools -----------------------------------------------------------


def place_order(items: str = "", table_number: int = 0, **kwargs: Any) -> dict[str, Any]:
    """
    Place a new order for the given items.

    Parameters
    ----------
    items : str
        Comma-separated list of menu item names (e.g. "Margherita Pizza, Tiramisu").
    table_number : int
        Table number for the order (0 = takeout).

    Returns
    -------
    dict
        Order confirmation with order_id, items, total, and estimated time.
    """
    items_str = items or kwargs.get("query", "")
    if not items_str:
        return {"error": "No items specified. Please provide comma-separated menu item names."}

    item_list = [i.strip() for i in items_str.split(",") if i.strip()]
    order_items = []
    unknown = []

    for item_name in item_list:
        price = _find_price(item_name)
        if price is not None:
            order_items.append({"name": item_name.title(), "qty": 1, "price": price})
        else:
            unknown.append(item_name)

    if not order_items:
        return {
            "error": "None of the requested items were found on the menu.",
            "unknown_items": unknown,
            "suggestion": "Use the search_menu tool to find available items.",
        }

    order_id = f"ORD-{uuid.uuid4().hex[:6].upper()}"
    subtotal = sum(i["price"] * i["qty"] for i in order_items)
    estimated_min = 15 + len(order_items) * 5

    order = {
        "order_id": order_id,
        "table_number": table_number,
        "items": order_items,
        "status": "confirmed",
        "estimated_time_min": estimated_min,
        "subtotal": round(subtotal, 2),
    }

    # Store for later lookup
    _ORDERS[order_id] = order

    result: dict[str, Any] = {
        "order_id": order_id,
        "table_number": table_number or "takeout",
        "items": order_items,
        "subtotal": round(subtotal, 2),
        "tax": round(subtotal * 0.08, 2),
        "total": round(subtotal * 1.08, 2),
        "estimated_time_min": estimated_min,
        "status": "confirmed",
        "message": f"Order {order_id} confirmed! Estimated time: {estimated_min} minutes.",
    }

    if unknown:
        result["warnings"] = f"Items not found and excluded: {', '.join(unknown)}"

    return result


def get_order_status(order_id: str = "", **kwargs: Any) -> dict[str, Any]:
    """
    Check the status of an existing order.

    Parameters
    ----------
    order_id : str
        The order identifier (e.g. "ORD-001").

    Returns
    -------
    dict
        Order status including items, progress, and estimated remaining time.
    """
    oid = order_id.strip().upper()
    if oid in _ORDERS:
        order = _ORDERS[oid]
        return {
            "order_id": oid,
            "status": order["status"],
            "table_number": order["table_number"],
            "items": order["items"],
            "estimated_time_min": order["estimated_time_min"],
            "special_requests": order.get("special_requests", ""),
        }

    return {
        "error": f"Order '{order_id}' not found.",
        "available_orders": list(_ORDERS.keys()),
        "suggestion": "Check the order ID and try again, or place a new order.",
    }


def calculate_bill(order_id: str = "", **kwargs: Any) -> dict[str, Any]:
    """
    Calculate the bill for a completed order.

    Parameters
    ----------
    order_id : str
        The order identifier (e.g. "ORD-001").

    Returns
    -------
    dict
        Itemized bill with subtotal, tax, service charge, and total.
    """
    oid = order_id.strip().upper()
    if oid not in _ORDERS:
        return {"error": f"Order '{order_id}' not found.", "available_orders": list(_ORDERS.keys())}

    order = _ORDERS[oid]
    items_detail = []
    subtotal = 0.0

    for item in order["items"]:
        line_total = item["price"] * item["qty"]
        items_detail.append({
            "name": item["name"],
            "quantity": item["qty"],
            "unit_price": item["price"],
            "line_total": round(line_total, 2),
        })
        subtotal += line_total

    tax = round(subtotal * 0.08, 2)
    service_charge = round(subtotal * 0.18, 2)
    total = round(subtotal + tax + service_charge, 2)

    return {
        "order_id": oid,
        "table_number": order["table_number"],
        "items": items_detail,
        "subtotal": round(subtotal, 2),
        "tax_8_pct": tax,
        "service_charge_18_pct": service_charge,
        "total": total,
        "payment_methods": ["cash", "credit card", "mobile pay"],
        "message": f"Bill for table {order['table_number']}: ${total:.2f} (incl. tax and 18% service charge).",
    }
