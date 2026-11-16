"""Deterministic account tools used by the intake example."""

from __future__ import annotations

_INVOICES = {
    "INV-1042": "INV-1042: charged twice on 2026-10-14 (two $49.00 charges); refund eligible.",
    "INV-2087": "INV-2087: single charge on 2026-10-02; no duplicate detected.",
}


def lookup_invoice(query: str = "", invoice_id: str = "") -> str:
    """Return a short invoice summary by id, or list the known invoices."""
    key = (invoice_id or "").strip().upper()
    if key in _INVOICES:
        return _INVOICES[key]
    return "Known invoices: " + ", ".join(sorted(_INVOICES))
