"""
Startup hook for the travel-agency example.

Demonstrates:
  - Dynamic tool registration via ``register_tool()``
  - Strategy registration via ``register_strategy()``
  - Seeding RAG with destination guide documents

Referenced in ``orchid.yml`` as::

    startup:
      hook: examples.travel-agency.hooks.startup.bootstrap_travel
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ── A tiny corpus of destination guides used as seed RAG data ──
_DESTINATIONS: list[dict[str, Any]] = [
    {
        "city": "London",
        "content": (
            "London highlights: British Museum (free), Tower of London, Hyde Park, "
            "West End theatres, markets (Borough, Camden, Portobello).  Typical "
            "spring weather: 10-18°C, rain likely.  Best neighbourhoods: Covent "
            "Garden, Mayfair, Shoreditch.  Transit: Oyster card or contactless."
        ),
    },
    {
        "city": "Paris",
        "content": (
            "Paris highlights: Louvre, Musée d'Orsay, Eiffel Tower, Montmartre, "
            "Le Marais, Notre-Dame (exterior only during restoration).  Spring: "
            "8-17°C, variable.  Book museums in advance.  Metro pass (Navigo) "
            "recommended for 3+ day stays."
        ),
    },
    {
        "city": "Tokyo",
        "content": (
            "Tokyo highlights: Shibuya Crossing, Tsukiji Outer Market, Asakusa, "
            "Meiji Shrine, teamLab Planets, Akihabara.  Spring: 12-20°C, "
            "cherry blossoms late March through early April.  Suica/Pasmo IC "
            "card for trains.  Most shops cash-preferred but card-accepted."
        ),
    },
    {
        "city": "Rome",
        "content": (
            "Rome highlights: Colosseum, Forum, Pantheon, Vatican Museums + St "
            "Peter's, Trastevere evenings.  Spring: 12-22°C.  Book Vatican and "
            "Colosseum entry online in advance.  Pickpockets on buses 64/40 and "
            "Termini area — carry essentials in front."
        ),
    },
]


async def bootstrap_travel(reader: Any, settings: Any, **_: Any) -> None:
    """Seed destination guides and register custom strategies.

    Signature matches ``STARTUP_HOOK`` contract: ``async (reader, settings)``.

    Parameters
    ----------
    reader : OrchidVectorReader
        The vector store backend.  If it also implements ``OrchidVectorWriter``,
        we can seed destination guides into the ``destinations`` namespace.
    settings
        The orchid-api Settings object (provider info, env, etc.).
    """
    # ── Register a custom tool at startup ──
    from orchid_ai.config.tool_registry import register_tool

    def estimate_trip_budget(
        nights: int = 0,
        nightly_usd: float = 0,
        flights_usd: float = 0,
        daily_meals_usd: float = 60,
        **_: Any,
    ) -> dict[str, Any]:
        """Rough budget estimate for a trip.  Returns lodging + flights + meals."""
        lodging = max(0, nights) * max(0, nightly_usd)
        meals = max(0, nights) * max(0, daily_meals_usd)
        total = lodging + flights_usd + meals
        return {
            "nights": nights,
            "lodging_usd": lodging,
            "flights_usd": flights_usd,
            "meals_usd": meals,
            "total_usd": total,
            "breakdown": (
                f"{nights} night(s) × ${nightly_usd}/night = ${lodging} lodging; "
                f"${flights_usd} flights; ${daily_meals_usd}/day × {nights} = ${meals} meals"
            ),
        }

    register_tool(
        "estimate_trip_budget",
        estimate_trip_budget,
        description="Estimate total trip cost (lodging + flights + meals).",
    )
    logger.info("[TravelAgency] Registered custom tool: estimate_trip_budget")

    # ── Seed destination guides into RAG ──
    try:
        from orchid_ai.core.repository import Document, OrchidVectorWriter
    except ImportError:
        logger.warning("[TravelAgency] orchid_ai not available — skipping RAG seed")
        return

    if not isinstance(reader, OrchidVectorWriter):
        logger.info("[TravelAgency] Reader does not support writing — skipping RAG seed")
        return

    documents = [
        Document(
            id=f"dest-{d['city'].lower()}",
            page_content=d["content"],
            metadata={
                "tenant_id": "__shared__",
                "city": d["city"],
                "scope": "tenant",
                "source": "destination_guide",
            },
        )
        for d in _DESTINATIONS
    ]

    try:
        await reader.upsert(documents, "destinations")
        logger.info("[TravelAgency] Seeded %d destination guides into RAG", len(documents))
    except Exception as exc:
        logger.warning("[TravelAgency] RAG seed failed: %s", exc)
