# Restaurant Example — Custom Agent with RAG

A restaurant ordering system demonstrating **custom agent classes**, **RAG with dynamic injection**, **sequential routing**, and **built-in tool orchestration**. Shows how to extend `OrchidAgent` for domain-specific logic while leveraging the framework's RAG and tool-calling capabilities.

## What It Demonstrates

- **Custom agent class** — `RestaurantAgent` extends `OrchidAgent` with domain-specific methods
- **RAG dynamic injection** — Menu items indexed and injected into agent context at runtime
- **Sequential routing** — Orders flow through `menu` → `orders` → `reviews` agents in sequence
- **Built-in tools** — `get_menu`, `place_order`, `submit_review` declared in YAML
- **Multi-turn conversation** — Order state preserved across conversation turns
- **Document upload** — PDF menu upload with image parsing via `minicpm-v`

## Features Highlighted

| Feature | Configuration |
|---------|--------------|
| Agent class | Custom `RestaurantAgent` subclass |
| RAG | Qdrant with dynamic injection at runtime |
| Routing | Sequential agent pipeline |
| Tools | Built-in Python functions with `@tool` decorator |
| Storage | SQLite (shared with basketball example) |
| Vision | `ollama/minicpm-v` for menu image parsing |
| LLM | Gemini (`gemini-flash-latest`, `gemini-embedding-001`) |

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   User       │────▶│   Menu Agent │────▶│  Order Agent │
│   (query)    │     │  (RAG lookup)│     │  (place order│
└──────────────┘     └──────────────┘     └──────────────┘
                            │                     │
                            ▼                     ▼
                     ┌──────────────┐     ┌──────────────┐
                     │  Vector DB   │     │  Order DB    │
                     │  (menu items)│     │  (orders)    │
                     └──────────────┘     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │ Review Agent │
                     │ (submit review)
                     └──────────────┘
```

## Prerequisites

- Gemini API key
- Ollama running with `ollama pull minicpm-v` (for menu image parsing)
- Python 3.11+ with `orchid-ai` and `orchid-api` installed

## Usage

### Via Docker Compose

```bash
# From repo root
docker compose -f docker-compose.demo.yml up --build
```

### Environment Variables

Create `.env.local` from `.env.example`:

```bash
cd examples/restaurant
cp .env.example .env.local
# Edit .env.local and set:
#   GEMINI_API_KEY=your_actual_key
```

### Via Standalone API

```bash
export GEMINI_API_KEY=your_key

ORCHID_CONFIG=examples/restaurant/config/orchid.yml \
  uvicorn orchid_api.main:app --port 8000
```

### Via CLI

```bash
export GEMINI_API_KEY=your_key

# Interactive session
orchid chat interactive --config examples/restaurant/config/orchid.yml

# Ask about menu items
orchid chat send "What vegetarian pasta dishes do you have?" \
  --config examples/restaurant/config/orchid.yml

# Place an order
orchid chat send "I'd like to order the Margherita pizza" \
  --agent orders \
  --config examples/restaurant/config/orchid.yml

# Upload a menu PDF
orchid chat upload menu.pdf \
  --config examples/restaurant/config/orchid.yml
```

## File Layout

```
examples/restaurant/
├── config/
│   ├── orchid.yml          # Runtime config (LLM, RAG, storage)
│   └── agents.yaml         # Three agents + tools
├── agents/
│   ├── __init__.py
│   └── reviews.py          # Custom ReviewsAgent class
├── tools/
│   ├── __init__.py
│   ├── menu.py             # get_menu, get_item_details
│   ├── orders.py           # place_order, get_order_status
│   └── reviews.py          # submit_review, get_reviews
└── .env.example            # Environment variable template
```

## Custom Agent Class

The `ReviewsAgent` (in `agents/reviews.py`) demonstrates how to extend `OrchidAgent`:

```python
class ReviewsAgent(OrchidAgent):
    """Restaurant reviews agent with domain-specific logic."""
    
    async def run(
        self,
        state: OrchidAgentState,
        auth_context: OrchidAuthContext,
    ) -> OrchidAgentState:
        # Extract review intent
        query = self.extract_user_query(state)
        
        # Check if user has existing orders (domain logic)
        has_order = await self._check_user_order_history(
            auth_context.user_id
        )
        
        if not has_order:
            return self._prompt_for_order(state)
        
        # Proceed with review submission
        return await super().run(state, auth_context)
    
    async def _check_user_order_history(
        self,
        user_id: str,
    ) -> bool:
        # Domain-specific database lookup
        ...
```

Key points:
- Inherits `self.summarise()`, `self.fetch_rag_context()`, `self.extract_conversation_history()` from parent
- Adds domain-specific methods for order history validation
- Can override `run()` for custom control flow

## RAG Configuration

### Indexing

Menu items are indexed with rich metadata:

```python
from orchid_ai.rag.scopes import OrchidRAGScope

scope = OrchidRAGScope(
    tenant_id="restaurant-demo",
    namespace="menu_items",
)

await writer.upsert(
    documents=[
        Document(
            page_content="Margherita Pizza - Fresh tomatoes, mozzarella, basil",
            metadata={
                "category": "pizza",
                "price": 14.99,
                "vegetarian": True,
                "allergens": ["dairy", "gluten"],
            },
        ),
    ],
    scope=scope,
)
```

### Retrieval

The `menu` agent uses RAG for semantic menu lookup:

```yaml
agents:
  menu:
    rag:
      enabled: true
      namespace: menu_items
      retrieval_strategy: simple
      top_k: 5
    prompt: |
      You are the Menu Assistant. Use RAG context to answer
      questions about dishes, ingredients, prices, and allergens.
```

### Dynamic Injection

RAG context is injected at runtime via `self.fetch_rag_context()`:

```python
async def run(self, state, auth_context):
    # Fetch relevant menu items from vector store
    context = await self.fetch_rag_context(
        query=state["messages"][-1].content,
        scope=scope,
    )
    
    # Augment prompt with retrieved context
    augmented_prompt = f"""
    Context from menu database:
    {context}
    
    User question: {state['messages'][-1].content}
    """
```

## Built-in Tools

Tools are declared in YAML and implemented in Python:

### YAML Declaration (`agents.yaml`)

```yaml
tools:
  get_menu:
    description: "Retrieve the full restaurant menu"
    parameters:
      category:
        type: string
        description: "Filter by category (pizza, pasta, salad, etc.)"
        required: false
      dietary:
        type: string
        description: "Filter by dietary restriction (vegetarian, vegan, GF)"
        required: false
```

### Python Implementation (`tools/menu.py`)

```python
@tool
async def get_menu(
    category: str | None = None,
    dietary: str | None = None,
    context: dict | None = None,
) -> str:
    """Retrieve menu items with optional filters."""
    # Query database or RAG context
    items = await query_menu_db(category=category, dietary=dietary)
    return format_menu_items(items)
```

Framework params (`context`, `auth_context`, `**kwargs`) are auto-filtered.

## Sequential Routing

The supervisor routes queries through agents in order:

```yaml
supervisor:
  assistant_name: "Restaurant Assistant"
  routing: sequential

agents:
  menu:      # First: answer menu questions
  orders:    # Second: place orders
  reviews:   # Third: handle reviews
```

Example flow:
1. User: "What pasta dishes do you have?" → `menu` agent (RAG lookup)
2. User: "I'll order the carbonara" → `orders` agent (place order)
3. User: "The food was great!" → `reviews` agent (submit review)

## Sample Interaction

```
User: What vegetarian options do you have?
Assistant: [fetches RAG context from menu_items namespace]
We have several vegetarian dishes:
- Margherita Pizza ($14.99) — tomatoes, mozzarella, basil
- Eggplant Parmesan ($16.99) — breaded eggplant, marinara, mozzarella
- Caprese Salad ($12.99) — fresh mozzarella, tomatoes, basil

User: I'll order the Margherita pizza
Assistant: [routes to orders agent]
Great choice! Would you like any sides or drinks with that?

User: Just the pizza, thanks
Assistant: [calls place_order tool]
Order #1234 placed! Your Margherita pizza will be ready in 15-20 minutes.
```

## Contrast with Other Examples

| Example | Custom Agent | RAG | Sequential | Tools |
|---------|-------------|-----|------------|-------|
| basketball | No | Optional | No | Built-in |
| helpdesk | Yes | Optional | Yes | Built-in |
| **restaurant** | **Yes** | **Yes (dynamic)** | **Yes** | **Built-in** |
| wiki | No | Yes (hybrid) | No | Built-in |

## Extending the Example

### Add a New Agent

```yaml
agents:
  reservations:
    class: examples.restaurant.agents.reservations.ReservationsAgent
    description: "Handle table reservations"
    prompt: |
      You are the Reservations Assistant. Help users book tables.
    tools:
      - make_reservation
      - cancel_reservation
      - check_availability
```

### Add Custom RAG Strategy

```python
from orchid_ai.rag.strategies import OrchidRAGStrategy

class PopularityWeightedStrategy(OrchidRAGStrategy):
    """Boost popular menu items in retrieval results."""
    
    async def retrieve(self, query, scope, **kwargs):
        results = await super().retrieve(query, scope)
        # Boost by order count metadata
        return sorted(results, key=lambda d: d.metadata.get("order_count", 0), reverse=True)
```

Register in `orchid.yml`:

```yaml
rag:
  strategies:
    popularity_weighted: examples.restaurant.rag.strategies.PopularityWeightedStrategy
```

## Next Steps

After exploring restaurant:
- **helpdesk** — Event-driven workflows with Pollen + Bloom
- **wiki** — Advanced RAG with hybrid retrieval
- **travel-agency** — HITL tool approval with checkpointer
