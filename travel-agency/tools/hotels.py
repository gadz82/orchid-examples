"""Built-in tools — Hotel search and availability (demo, static data)."""

from __future__ import annotations

from typing import Any

_HOTELS: list[dict[str, Any]] = [
    {
        "hotel_id": "HTL-LON-001",
        "name": "The Strand Palace",
        "city": "London",
        "stars": 4,
        "nightly_usd": 210,
        "amenities": ["wifi", "breakfast", "gym", "bar"],
        "available_rooms": 18,
        "near_landmarks": ["Covent Garden", "Trafalgar Square"],
    },
    {
        "hotel_id": "HTL-LON-002",
        "name": "Mayfair Residence",
        "city": "London",
        "stars": 5,
        "nightly_usd": 520,
        "amenities": ["wifi", "breakfast", "gym", "spa", "concierge"],
        "available_rooms": 6,
        "near_landmarks": ["Hyde Park", "Bond Street"],
    },
    {
        "hotel_id": "HTL-PAR-001",
        "name": "Hotel Montmartre",
        "city": "Paris",
        "stars": 3,
        "nightly_usd": 140,
        "amenities": ["wifi", "breakfast"],
        "available_rooms": 25,
        "near_landmarks": ["Sacré-Cœur", "Pigalle"],
    },
    {
        "hotel_id": "HTL-PAR-002",
        "name": "Le Marais Boutique",
        "city": "Paris",
        "stars": 4,
        "nightly_usd": 280,
        "amenities": ["wifi", "breakfast", "bar", "terrace"],
        "available_rooms": 11,
        "near_landmarks": ["Notre-Dame", "Le Marais"],
    },
    {
        "hotel_id": "HTL-TYO-001",
        "name": "Shibuya Sky",
        "city": "Tokyo",
        "stars": 4,
        "nightly_usd": 190,
        "amenities": ["wifi", "breakfast", "gym", "onsen"],
        "available_rooms": 32,
        "near_landmarks": ["Shibuya Crossing", "Harajuku"],
    },
    {
        "hotel_id": "HTL-TYO-002",
        "name": "Imperial Gardens",
        "city": "Tokyo",
        "stars": 5,
        "nightly_usd": 610,
        "amenities": ["wifi", "breakfast", "spa", "michelin restaurant"],
        "available_rooms": 4,
        "near_landmarks": ["Imperial Palace", "Ginza"],
    },
    {
        "hotel_id": "HTL-ROM-001",
        "name": "Via Veneto Classic",
        "city": "Rome",
        "stars": 4,
        "nightly_usd": 230,
        "amenities": ["wifi", "breakfast", "rooftop pool"],
        "available_rooms": 14,
        "near_landmarks": ["Trevi Fountain", "Spanish Steps"],
    },
]


def search_hotels(
    city: str = "",
    min_stars: int = 0,
    max_nightly_usd: float = 0,
    required_amenity: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    """Search hotels by city, rating, price, and required amenity."""
    city_l = (city or "").strip().lower()
    amenity_l = (required_amenity or "").strip().lower()

    matches = []
    for hotel in _HOTELS:
        if city_l and hotel["city"].lower() != city_l:
            continue
        if min_stars > 0 and hotel["stars"] < min_stars:
            continue
        if max_nightly_usd > 0 and hotel["nightly_usd"] > max_nightly_usd:
            continue
        if amenity_l and amenity_l not in [a.lower() for a in hotel["amenities"]]:
            continue
        matches.append(hotel)

    matches.sort(key=lambda h: (-h["stars"], h["nightly_usd"]))

    return {
        "query": {
            "city": city_l or "any",
            "min_stars": min_stars or None,
            "max_nightly_usd": max_nightly_usd or None,
            "required_amenity": amenity_l or None,
        },
        "count": len(matches),
        "hotels": matches,
    }


def get_hotel_details(hotel_id: str = "", **kwargs: Any) -> dict[str, Any]:
    """Look up a specific hotel by its ID."""
    hid = (hotel_id or "").strip().upper()
    for hotel in _HOTELS:
        if hotel["hotel_id"] == hid:
            return {**hotel}
    return {
        "error": f"Hotel '{hid}' not found",
        "available_hotels": [h["hotel_id"] for h in _HOTELS],
    }
