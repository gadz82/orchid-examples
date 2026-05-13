"""
Startup hook for the recipes example.

Seeds a small recipe corpus into the ``recipes`` namespace so agents
have material to retrieve.  Runs best-effort — if the vector store
is not writable or fails, the agents still start (they just return
empty results).

Wire-up (orchid.yml)::

    startup:
      hook: examples.recipes.hooks.startup.seed_recipes
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_RECIPES: list[dict[str, Any]] = [
    {
        "id": "chicken-parmesan",
        "content": (
            "Chicken Parmesan — Crispy breaded chicken cutlets topped "
            "with marinara sauce and melted mozzarella.  Serves 4.\n\n"
            "Ingredients: 4 boneless chicken breasts, 1 cup breadcrumbs, "
            "1/2 cup grated Parmesan, 2 eggs, 2 cups marinara sauce, "
            "2 cups shredded mozzarella, salt, pepper, olive oil.\n\n"
            "Steps: 1) Pound chicken to 1/2-inch thickness.  "
            "2) Mix breadcrumbs with Parmesan.  3) Dip chicken in "
            "beaten eggs, then breadcrumb mix.  4) Pan-fry in oil "
            "until golden, 3 min per side.  5) Top with sauce and "
            "cheese, bake at 400F for 15 min."
        ),
        "metadata": {
            "cuisine": "italian",
            "course": "main",
            "prep_time_min": 35,
            "dietary": "contains_dairy",
            "difficulty": "medium",
            "ingredients": "chicken,parmesan,marinara,breadcrumbs,eggs,cheese",
        },
    },
    {
        "id": "vegetable-stir-fry",
        "content": (
            "Vegetable Stir-Fry — Quick, colorful vegetable medley with "
            "a savoury soy-ginger sauce.  Serves 2.\n\n"
            "Ingredients: 2 cups broccoli florets, 1 red bell pepper "
            "(sliced), 1 carrot (julienned), 1 cup snap peas, 3 tbsp "
            "soy sauce, 1 tbsp ginger (grated), 2 cloves garlic "
            "(minced), 2 tbsp vegetable oil, 1 tbsp sesame seeds.\n\n"
            "Steps: 1) Heat oil in wok over high heat.  2) Stir-fry "
            "broccoli and carrot for 2 min.  3) Add bell pepper and "
            "snap peas, cook 1 min.  4) Add garlic and ginger, cook "
            "30 seconds.  5) Pour in soy sauce, toss to coat.  "
            "6) Garnish with sesame seeds, serve over rice."
        ),
        "metadata": {
            "cuisine": "asian",
            "course": "main",
            "prep_time_min": 15,
            "dietary": "vegan,gluten_free_option",
            "difficulty": "easy",
            "ingredients": "broccoli,bell_pepper,carrot,snap_peas,soy_sauce,ginger,garlic",
        },
    },
    {
        "id": "chocolate-cake",
        "content": (
            "Classic Chocolate Cake — Rich, moist layer cake with "
            "chocolate buttercream frosting.  Serves 10.\n\n"
            "Ingredients: 2 cups all-purpose flour, 2 cups sugar, "
            "3/4 cup cocoa powder, 2 tsp baking soda, 1 tsp baking "
            "powder, 1 tsp salt, 1 cup buttermilk, 1/2 cup vegetable "
            "oil, 2 eggs, 2 tsp vanilla extract, 1 cup hot coffee.\n\n"
            "Steps: 1) Preheat oven to 350F, grease two 9-inch pans.  "
            "2) Whisk dry ingredients.  3) Add buttermilk, oil, eggs, "
            "vanilla, beat 2 min.  4) Stir in hot coffee (batter will "
            "be thin).  5) Divide between pans, bake 30-35 min.  "
            "6) Cool completely, frost with chocolate buttercream."
        ),
        "metadata": {
            "cuisine": "american",
            "course": "dessert",
            "prep_time_min": 60,
            "dietary": "contains_dairy,contains_gluten",
            "difficulty": "medium",
            "ingredients": "flour,sugar,cocoa,buttermilk,eggs,butter,coffee",
        },
    },
    {
        "id": "caesar-salad",
        "content": (
            "Classic Caesar Salad — Crisp romaine with homemade "
            "Caesar dressing, croutons, and Parmesan.  Serves 4.\n\n"
            "Ingredients: 1 head romaine lettuce, 1/2 cup Caesar "
            "dressing, 1 cup croutons, 1/2 cup shaved Parmesan, "
            "1 lemon.\n\n"
            "Caesar Dressing: 2 anchovy fillets, 1 clove garlic, "
            "2 tbsp lemon juice, 1 tsp Dijon mustard, 1 tsp "
            "Worcestershire sauce, 1/2 cup olive oil, 1/4 cup "
            "Parmesan, salt, pepper.\n\n"
            "Steps: 1) Mash anchovies and garlic into paste.  "
            "2) Whisk in lemon juice, mustard, Worcestershire.  "
            "3) Slowly drizzle oil while whisking.  4) Stir in "
            "Parmesan, season.  5) Toss torn romaine with dressing, "
            "top with croutons and shaved Parmesan."
        ),
        "metadata": {
            "cuisine": "italian",
            "course": "starter",
            "prep_time_min": 15,
            "dietary": "contains_dairy",
            "difficulty": "easy",
            "ingredients": "romaine,parmesan,croutons,anchovy,garlic,lemon,olive_oil",
        },
    },
    {
        "id": "lentil-soup",
        "content": (
            "Hearty Lentil Soup — Warming, protein-packed soup with "
            "vegetables and aromatic spices.  Serves 6.\n\n"
            "Ingredients: 2 cups dried green lentils, 1 onion (diced), "
            "2 carrots (diced), 3 celery stalks (diced), 4 cloves "
            "garlic (minced), 1 can diced tomatoes, 6 cups vegetable "
            "broth, 2 tsp cumin, 1 tsp turmeric, salt, pepper, "
            "2 tbsp olive oil, 2 tbsp lemon juice.\n\n"
            "Steps: 1) Sauté onion, carrot, celery in oil until soft, "
            "8 min.  2) Add garlic and spices, cook 1 min.  "
            "3) Add lentils, tomatoes, broth.  Bring to boil.  "
            "4) Simmer 30-35 min until lentils are tender.  "
            "5) Stir in lemon juice, season to taste."
        ),
        "metadata": {
            "cuisine": "middle_eastern",
            "course": "main",
            "prep_time_min": 45,
            "dietary": "vegan,gluten_free",
            "difficulty": "easy",
            "ingredients": "lentils,onion,carrot,celery,garlic,tomatoes,cumin,turmeric",
        },
    },
    {
        "id": "guacamole",
        "content": (
            "Fresh Guacamole — Creamy avocado dip with lime, cilantro, "
            "and jalapeño.  Serves 4 as a starter.\n\n"
            "Ingredients: 3 ripe avocados, 1 lime (juiced), 1/4 cup "
            "finely diced red onion, 1 jalapeño (seeded and minced), "
            "1/4 cup chopped cilantro, 1 Roma tomato (diced), salt.\n\n"
            "Steps: 1) Halve avocados, remove pit, scoop into bowl.  "
            "2) Mash to desired consistency.  3) Stir in lime juice, "
            "onion, jalapeño, cilantro, tomato.  4) Season with salt.  "
            "5) Serve immediately with tortilla chips."
        ),
        "metadata": {
            "cuisine": "mexican",
            "course": "starter",
            "prep_time_min": 10,
            "dietary": "vegan,gluten_free",
            "difficulty": "easy",
            "ingredients": "avocado,lime,onion,jalapeno,cilantro,tomato",
        },
    },
    {
        "id": "pad-thai",
        "content": (
            "Pad Thai — Classic Thai rice noodle stir-fry with tamarind "
            "sauce, shrimp, peanuts, and bean sprouts.  Serves 2.\n\n"
            "Ingredients: 8 oz rice noodles, 8 oz shrimp (peeled), "
            "3 tbsp tamarind paste, 2 tbsp fish sauce, 1 tbsp sugar, "
            "1 tbsp lime juice, 2 eggs, 1 cup bean sprouts, "
            "1/4 cup crushed peanuts, 2 green onions (sliced), "
            "2 tbsp vegetable oil.\n\n"
            "Steps: 1) Soak noodles in warm water 30 min, drain.  "
            "2) Mix tamarind, fish sauce, sugar, lime juice.  "
            "3) Heat oil in wok, cook shrimp 2 min, set aside.  "
            "4) Scramble eggs in the wok.  5) Add noodles and sauce, "
            "toss 2 min.  6) Return shrimp, add bean sprouts and "
            "green onions.  7) Plate, top with crushed peanuts."
        ),
        "metadata": {
            "cuisine": "thai",
            "course": "main",
            "prep_time_min": 40,
            "dietary": "contains_shellfish,gluten_free",
            "difficulty": "medium",
            "ingredients": "rice_noodles,shrimp,tamarind,fish_sauce,eggs,peanuts,lime",
        },
    },
    {
        "id": "banana-bread",
        "content": (
            "Moist Banana Bread — Perfect way to use overripe bananas.  "
            "Simple, one-bowl recipe.  Makes 1 loaf.\n\n"
            "Ingredients: 3 ripe bananas (mashed), 1/3 cup melted "
            "butter, 3/4 cup sugar, 1 egg, 1 tsp vanilla, 1 tsp "
            "baking soda, pinch of salt, 1.5 cups all-purpose flour.\n\n"
            "Steps: 1) Preheat oven to 350F, grease 9x5 loaf pan.  "
            "2) Mash bananas in a bowl, stir in melted butter.  "
            "3) Mix in sugar, egg, vanilla.  4) Add baking soda, "
            "salt, flour, stir until just combined (do not overmix).  "
            "5) Pour batter into pan, bake 55-60 min.  "
            "6) Cool 10 min in pan, then turn out onto rack."
        ),
        "metadata": {
            "cuisine": "american",
            "course": "dessert",
            "prep_time_min": 70,
            "dietary": "vegetarian",
            "difficulty": "easy",
            "ingredients": "bananas,butter,sugar,eggs,vanilla,flour",
        },
    },
]


async def seed_recipes(reader: Any, settings: Any, **_: Any) -> None:
    """Seed the recipe corpus into the vector store.

    Best-effort — logs a warning on failure but does not crash the
    bootstrap so the agents are still available (they'll just return
    empty RAG results).
    """
    try:
        from orchid_ai.core.repository import Document, OrchidVectorWriter
    except ImportError:
        logger.warning("[Recipes] orchid_ai not available — skipping seed")
        return

    if not isinstance(reader, OrchidVectorWriter):
        logger.info("[Recipes] Reader is not a writer — skipping seed")
        return

    documents = [
        Document(
            id=recipe["id"],
            page_content=recipe["content"],
            metadata={
                "tenant_id": "__shared__",
                "scope": "tenant",
                **recipe["metadata"],
            },
        )
        for recipe in _RECIPES
    ]

    try:
        await reader.upsert(documents, "recipes")
        logger.info("[Recipes] Seeded %d recipes into 'recipes' namespace", len(documents))
    except Exception as exc:
        logger.warning("[Recipes] RAG seed failed: %s", exc)
