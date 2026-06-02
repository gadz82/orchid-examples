"""Startup hook for the weather example.

Demonstrates:
  - Seeding RAG with clothing guide documents
  - Seeding RAG with weather safety guide documents

Referenced in ``orchid.yml`` as::

    startup:
      hook: examples.weather.hooks.startup.bootstrap_weather
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Clothing guides seeded into the ``clothing-guides`` RAG namespace ──
_CLOTHING_GUIDES: list[dict[str, Any]] = [
    {
        "guide_id": "hot-weather",
        "content": (
            "Hot weather (above 25°C / 77°F): Wear lightweight, breathable fabrics "
            "like cotton, linen, or moisture-wicking synthetics. Light colours reflect "
            "sunlight. Loose-fitting clothes allow airflow. Essential accessories: "
            "wide-brimmed hat, sunglasses with UV protection, sunscreen SPF 30+. "
            "Footwear: open sandals or breathable sneakers. Avoid dark colours and "
            "heavy fabrics like denim or wool. For exercise: technical moisture-wicking "
            "fabrics prevent chafing. Always carry water."
        ),
    },
    {
        "guide_id": "warm-weather",
        "content": (
            "Warm weather (15-25°C / 59-77°F): Layer with a light base (t-shirt, "
            "blouse) and bring a light jacket, cardigan, or hoodie for cooler moments. "
            "Versatile bottoms: chinos, light jeans, midi skirts. Footwear: sneakers, "
            "loafers, or closed-toe sandals. The key is layering — mornings and "
            "evenings can be significantly cooler than midday. A light scarf adds "
            "warmth without bulk. Umbrella recommended if rain chance is above 40%."
        ),
    },
    {
        "guide_id": "cool-weather",
        "content": (
            "Cool weather (5-15°C / 41-59°F): Base layer (long-sleeve shirt, "
            "turtleneck), mid layer (sweater, fleece, cardigan), outer layer (jacket, "
            "trench coat, or light puffer). Bottoms: jeans, wool trousers, or lined "
            "pants. Footwear: leather boots, ankle boots, or warm sneakers with wool "
            "socks. Accessories: light scarf, thin gloves if below 8°C. Layering is "
            "critical — you can remove layers when indoors or if the sun comes out."
        ),
    },
    {
        "guide_id": "cold-weather",
        "content": (
            "Cold weather (below 5°C / 41°F): Thermal base layer (merino wool or "
            "synthetic), insulating mid layer (fleece, down vest, thick wool sweater), "
            "windproof and waterproof outer layer. Bottoms: insulated pants, fleece-lined "
            "leggings under trousers, or snow pants for outdoor activities. Footwear: "
            "insulated waterproof boots with thick wool socks. Essential accessories: "
            "warm hat/beanie (30% of body heat lost through head), insulated gloves or "
            "mittens, thick scarf or neck gaiter. Cover all exposed skin — frostbite "
            "risk below -5°C."
        ),
    },
    {
        "guide_id": "rainy-weather",
        "content": (
            "Rainy weather: Waterproof is the priority. Outer layer: waterproof jacket "
            "with sealed seams, or a quality raincoat. Avoid umbrellas in windy rain "
            "(they invert). Footwear: waterproof boots or treated leather shoes — wet "
            "feet lead to blisters and rapid heat loss. Bottoms: quick-dry fabrics or "
            "waterproof overtrousers. Avoid cotton jeans in heavy rain (they stay wet "
            "for hours). Accessories: waterproof bag or bag cover for electronics. "
            "A baseball cap under your hood improves visibility in driving rain."
        ),
    },
    {
        "guide_id": "windy-weather",
        "content": (
            "Windy weather: Wind chill makes air temperature feel 5-15°C colder. "
            "A windproof outer shell is the most important piece. Avoid loose, flapping "
            "clothing (scarves with long ends, wide skirts, loose hoods). Tighter fits "
            "reduce wind penetration. Footwear: sturdy shoes (wind can unbalance you). "
            "Accessories: secure hat that won't blow off, wraparound sunglasses against "
            "debris. For cycling or motorcycling: windproof gloves, full-face protection. "
            "Always check the wind chill equivalent temperature, not just the air temperature."
        ),
    },
    {
        "guide_id": "snowy-weather",
        "content": (
            "Snowy weather: Insulation AND waterproofing are both essential — snow "
            "melts on contact with body heat and soaks through non-waterproof fabrics. "
            "Layers: thermal base, fleece mid, waterproof/insulated outer. Footwear: "
            "insulated snow boots with deep tread for traction — Yaktrax or microspikes "
            "for icy conditions. Accessories: waterproof gloves (not just knit — they "
            "get wet and freeze), thermal hat that covers ears, neck gaiter. Sunglasses "
            "or goggles (snow reflects 80% of UV). Change out of wet clothes immediately "
            "when indoors."
        ),
    },
]

# ── Safety guides seeded into the ``safety-guides`` RAG namespace ──
_SAFETY_GUIDES: list[dict[str, Any]] = [
    {
        "guide_id": "emergency-kit",
        "content": (
            "Emergency preparedness kit essentials: Water (4 litres per person per day, "
            "minimum 3-day supply). Non-perishable food (3-day supply). Manual can "
            "opener. Flashlight with extra batteries or hand-crank. First aid kit with "
            "prescription medications. Multi-tool or Swiss Army knife. Battery-powered "
            "or hand-crank radio. Mobile phone with portable charger and backup battery. "
            "Cash in small bills. Copies of important documents (ID, insurance, medical "
            "records) in a waterproof container. Whistle to signal for help. Dust mask. "
            "Plastic sheeting and duct tape for shelter. Moist towelettes and garbage "
            "bags for sanitation. Wrench or pliers to turn off utilities. Local maps. "
            "Pet food and extra water for pets. Store in a portable container."
        ),
    },
    {
        "guide_id": "heat-safety",
        "content": (
            "Heat safety guidelines: Drink 250-500ml of water every hour in extreme heat, "
            "even if not thirsty. Avoid alcohol and caffeine (they dehydrate). Wear "
            "lightweight, light-coloured, loose-fitting clothes. Schedule outdoor "
            "activities for early morning or evening. Take cool showers or baths. "
            "Use fans only when temperature is below 35°C — above that, fans worsen "
            "dehydration. Know the signs: heat cramps (muscle spasms), heat exhaustion "
            "(heavy sweating, pale skin, nausea), heat stroke (hot skin, confusion, "
            "unconsciousness — call 911 immediately). Check on elderly relatives twice "
            "daily during heatwaves. NEVER leave anyone in a parked car."
        ),
    },
    {
        "guide_id": "flood-safety",
        "content": (
            "Flood safety: TURN AROUND, DON'T DROWN. Just 15cm (6 inches) of moving "
            "water can knock an adult down. 30cm (12 inches) can sweep away most cars. "
            "60cm (2 feet) can sweep away SUVs and trucks. Never drive around barricades "
            "— they are there for your safety. Move to higher ground immediately when "
            "flooding starts. Avoid contact with flood water (sewage, chemicals, "
            "submerged hazards). Do not touch electrical equipment if wet. Listen for "
            "evacuation orders via radio, TV, or phone alerts. After flooding: do not "
            "return home until authorities say it's safe, watch for snakes and animals, "
            "photograph damage for insurance, throw away any food that contacted flood "
            "water."
        ),
    },
    {
        "guide_id": "winter-safety",
        "content": (
            "Winter storm safety: Stay indoors during severe storms. If you must go out, "
            "tell someone your route and expected arrival time. Dress in layers with a "
            "windproof outer shell. Watch for signs of frostbite: numbness, white or "
            "greyish-yellow skin, firm or waxy feel. Hypothermia signs: shivering, "
            "exhaustion, confusion, fumbling hands, memory loss, slurred speech, "
            "drowsiness. If stranded in a vehicle: stay inside, run the engine 10 minutes "
            "per hour for heat (with a slightly open window for ventilation), clear the "
            "exhaust pipe of snow, tie a brightly coloured cloth to the antenna, move "
            "arms and legs to maintain circulation, huddle with passengers."
        ),
    },
]


async def bootstrap_weather(reader: Any, settings: Any, **_: Any) -> None:
    """Seed clothing and safety guides into RAG namespaces.

    Signature matches ``STARTUP_HOOK`` contract: ``async (reader, settings)``.

    Parameters
    ----------
    reader : OrchidVectorReader
        The vector store backend. If it also implements ``OrchidVectorWriter``,
        we can seed guides into the ``clothing-guides`` and ``safety-guides`` namespaces.
    settings
        The orchid-api Settings object (provider info, env, etc.).
    """
    try:
        from orchid_ai.core.repository import Document, OrchidVectorWriter
    except ImportError:
        logger.warning("[Weather] orchid_ai not available — skipping RAG seed")
        return

    if not isinstance(reader, OrchidVectorWriter):
        logger.info("[Weather] Reader does not support writing — skipping RAG seed")
        return

    # ── Seed clothing guides ──
    clothing_docs = [
        Document(
            id=f"clothing-{g['guide_id']}",
            page_content=g["content"],
            metadata={
                "tenant_id": "__shared__",
                "guide_id": g["guide_id"],
                "scope": "tenant",
                "source": "clothing_guide",
            },
        )
        for g in _CLOTHING_GUIDES
    ]

    try:
        await reader.upsert(clothing_docs, "clothing-guides")
        logger.info("[Weather] Seeded %d clothing guides into RAG", len(clothing_docs))
    except Exception as exc:
        logger.warning("[Weather] Clothing guide RAG seed failed: %s", exc)

    # ── Seed safety guides ──
    safety_docs = [
        Document(
            id=f"safety-{g['guide_id']}",
            page_content=g["content"],
            metadata={
                "tenant_id": "__shared__",
                "guide_id": g["guide_id"],
                "scope": "tenant",
                "source": "safety_guide",
            },
        )
        for g in _SAFETY_GUIDES
    ]

    try:
        await reader.upsert(safety_docs, "safety-guides")
        logger.info("[Weather] Seeded %d safety guides into RAG", len(safety_docs))
    except Exception as exc:
        logger.warning("[Weather] Safety guide RAG seed failed: %s", exc)
