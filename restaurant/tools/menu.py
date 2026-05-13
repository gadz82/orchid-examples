"""
Built-in tools — restaurant menu search and daily specials.

All data is static / in-memory.  No external API calls.
Functions accept ``**kwargs`` to absorb extra arguments
(``query``, ``context``) that GenericAgent passes automatically.
"""

from __future__ import annotations

from typing import Any

# -- Static menu database ---------------------------------------------------

_MENU: dict[str, dict[str, Any]] = {
    "margherita pizza": {
        "name": "Margherita Pizza",
        "category": "pizza",
        "price": 14.99,
        "ingredients": ["tomato sauce", "mozzarella", "fresh basil", "olive oil"],
        "allergens": ["gluten", "dairy"],
        "dietary": ["vegetarian"],
        "calories": 820,
        "description": "Classic Neapolitan pizza with San Marzano tomatoes and buffalo mozzarella.",
    },
    "truffle mushroom risotto": {
        "name": "Truffle Mushroom Risotto",
        "category": "pasta & risotto",
        "price": 22.50,
        "ingredients": ["arborio rice", "porcini mushrooms", "truffle oil", "parmesan", "white wine"],
        "allergens": ["dairy"],
        "dietary": ["vegetarian", "gluten-free"],
        "calories": 680,
        "description": "Creamy risotto with wild porcini mushrooms and a drizzle of black truffle oil.",
    },
    "grilled salmon": {
        "name": "Grilled Atlantic Salmon",
        "category": "seafood",
        "price": 28.00,
        "ingredients": ["atlantic salmon", "lemon", "capers", "asparagus", "dill butter"],
        "allergens": ["fish", "dairy"],
        "dietary": ["gluten-free", "high-protein"],
        "calories": 540,
        "description": "Pan-seared salmon fillet with lemon-caper butter and roasted asparagus.",
    },
    "caesar salad": {
        "name": "Classic Caesar Salad",
        "category": "salad",
        "price": 12.50,
        "ingredients": ["romaine lettuce", "parmesan", "croutons", "caesar dressing", "anchovies"],
        "allergens": ["gluten", "dairy", "fish"],
        "dietary": [],
        "calories": 380,
        "description": "Crisp romaine with house-made Caesar dressing, shaved parmesan, and garlic croutons.",
    },
    "vegan buddha bowl": {
        "name": "Vegan Buddha Bowl",
        "category": "bowl",
        "price": 16.99,
        "ingredients": ["quinoa", "roasted chickpeas", "avocado", "sweet potato", "tahini dressing"],
        "allergens": ["sesame"],
        "dietary": ["vegan", "gluten-free", "dairy-free"],
        "calories": 520,
        "description": "Nourishing bowl with roasted sweet potato, chickpeas, avocado, and tahini drizzle.",
    },
    "filet mignon": {
        "name": "Filet Mignon",
        "category": "steak",
        "price": 42.00,
        "ingredients": ["beef tenderloin", "red wine reduction", "garlic mashed potatoes", "green beans"],
        "allergens": ["dairy"],
        "dietary": ["gluten-free", "high-protein"],
        "calories": 720,
        "description": "8oz prime beef tenderloin with red wine jus, garlic mash, and haricots verts.",
    },
    "tiramisu": {
        "name": "Classic Tiramisu",
        "category": "dessert",
        "price": 11.00,
        "ingredients": ["mascarpone", "espresso", "ladyfingers", "cocoa powder", "marsala wine"],
        "allergens": ["gluten", "dairy", "eggs"],
        "dietary": ["vegetarian"],
        "calories": 450,
        "description": "Traditional Italian tiramisu with layers of espresso-soaked ladyfingers and mascarpone cream.",
    },
    "spicy thai curry": {
        "name": "Spicy Thai Green Curry",
        "category": "curry",
        "price": 18.50,
        "ingredients": ["coconut milk", "green curry paste", "tofu", "bamboo shoots", "thai basil", "jasmine rice"],
        "allergens": ["soy"],
        "dietary": ["vegan", "gluten-free", "dairy-free"],
        "calories": 580,
        "description": "Fragrant green curry with crispy tofu, bamboo shoots, and steamed jasmine rice.",
    },
}

_DAILY_SPECIALS = [
    {
        "name": "Pan-Seared Duck Breast",
        "price": 34.00,
        "description": "Duck breast with cherry gastrique, roasted root vegetables, and wild rice pilaf.",
        "available_until": "10:00 PM",
    },
    {
        "name": "Lobster Linguine",
        "price": 38.00,
        "description": "Fresh Maine lobster tossed with linguine in a light saffron cream sauce.",
        "available_until": "9:30 PM",
    },
]


def _match_items(query: str, dietary_filter: str = "") -> list[dict[str, Any]]:
    """Return menu items matching query text and optional dietary filter."""
    query_lower = query.strip().lower()
    diet_lower = dietary_filter.strip().lower()

    results = []
    for key, item in _MENU.items():
        # Text match: name, category, ingredients, or description
        text_match = (
            not query_lower
            or query_lower in key
            or query_lower in item["category"].lower()
            or query_lower in item["description"].lower()
            or any(query_lower in ing for ing in item["ingredients"])
        )
        # Dietary filter
        diet_match = (
            not diet_lower
            or diet_lower in [d.lower() for d in item["dietary"]]
        )
        if text_match and diet_match:
            results.append(item)

    return results


# -- Public tools -----------------------------------------------------------


def search_menu(query: str = "", dietary_filter: str = "", **kwargs: Any) -> dict[str, Any]:
    """
    Search the restaurant menu by keyword and optional dietary preference.

    Parameters
    ----------
    query : str
        Search term (matches name, category, ingredients, description).
    dietary_filter : str
        Filter by dietary label: vegetarian, vegan, gluten-free, dairy-free, high-protein.

    Returns
    -------
    dict
        Matching menu items with prices, ingredients, allergens, and dietary info.
    """
    q = query or kwargs.get("query", "")
    results = _match_items(q, dietary_filter)

    if not results:
        return {
            "matches": [],
            "message": f"No menu items found for '{q}'" + (f" with filter '{dietary_filter}'" if dietary_filter else ""),
            "suggestion": "Try broader terms like 'pizza', 'salad', 'vegan', or 'seafood'.",
        }

    return {
        "matches": results,
        "count": len(results),
        "query": q,
        "dietary_filter": dietary_filter or "none",
    }


def get_daily_specials(**kwargs: Any) -> dict[str, Any]:
    """
    Get today's daily specials.

    Returns
    -------
    dict
        List of today's special dishes with prices and availability.
    """
    return {
        "specials": _DAILY_SPECIALS,
        "count": len(_DAILY_SPECIALS),
        "note": "Daily specials are available while supplies last. Ask your server for details.",
    }
