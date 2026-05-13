"""
Built-in tools — Helpdesk ticket management and knowledge base (demo).

All data is static / in-memory.  No external API calls.
Functions accept ``**kwargs`` to absorb extra arguments
(``query``, ``context``) that GenericAgent passes automatically.
"""

from __future__ import annotations

import random
from typing import Any

# ── Static knowledge base ──────────────────────────────────────────

_KB_ARTICLES: list[dict[str, Any]] = [
    {
        "id": "KB-001",
        "title": "How to reset your password",
        "category": "authentication",
        "content": (
            "Navigate to Settings > Security > Change Password. "
            "Enter your current password, then your new password twice. "
            "If you forgot your current password, use the 'Forgot Password' "
            "link on the login page to receive a reset email."
        ),
        "tags": ["password", "login", "authentication", "reset"],
    },
    {
        "id": "KB-002",
        "title": "Configuring SSO with SAML 2.0",
        "category": "authentication",
        "content": (
            "Go to Admin > Integrations > SSO Configuration. "
            "Upload your IdP metadata XML or enter the SSO URL, Entity ID, "
            "and X.509 certificate manually. Test the connection before enabling. "
            "Supported IdPs: Okta, Azure AD, OneLogin, PingIdentity."
        ),
        "tags": ["sso", "saml", "authentication", "integration"],
    },
    {
        "id": "KB-003",
        "title": "API rate limits and throttling",
        "category": "api",
        "content": (
            "The default rate limit is 100 requests/minute per API key. "
            "Enterprise plans support up to 1000 req/min. When throttled, "
            "the API returns HTTP 429 with a Retry-After header. "
            "Implement exponential backoff in your integration code."
        ),
        "tags": ["api", "rate-limit", "throttling", "integration"],
    },
    {
        "id": "KB-004",
        "title": "Troubleshooting email delivery issues",
        "category": "email",
        "content": (
            "Check Admin > Notifications > Email Logs for bounce/reject status. "
            "Common causes: SPF/DKIM misconfiguration, recipient mailbox full, "
            "domain blacklisted. Verify your sending domain DNS records. "
            "For SMTP relay, ensure port 587 TLS is not blocked by your firewall."
        ),
        "tags": ["email", "notifications", "smtp", "dns"],
    },
    {
        "id": "KB-005",
        "title": "Data export and GDPR compliance",
        "category": "compliance",
        "content": (
            "Use Admin > Data Management > Export to generate a full data export "
            "in CSV or JSON format. For GDPR subject access requests, use the "
            "dedicated SAR endpoint: POST /api/v1/gdpr/sar. Data deletion requests "
            "are processed within 30 days per our data processing agreement."
        ),
        "tags": ["gdpr", "export", "compliance", "data", "privacy"],
    },
    {
        "id": "KB-006",
        "title": "Webhook configuration and retry policy",
        "category": "integration",
        "content": (
            "Configure webhooks at Admin > Integrations > Webhooks. "
            "Events: user.created, course.completed, enrollment.updated. "
            "Webhooks retry 3 times with exponential backoff (1s, 5s, 25s). "
            "Payloads are signed with HMAC-SHA256; verify using the webhook secret."
        ),
        "tags": ["webhook", "integration", "api", "events"],
    },
]

# ── Static ticket database ─────────────────────────────────────────

_TICKETS: dict[str, dict[str, Any]] = {
    "TK-1001": {
        "ticket_id": "TK-1001",
        "subject": "Cannot login after password reset",
        "status": "open",
        "priority": "high",
        "category": "authentication",
        "assigned_to": "support",
        "created_at": "2026-04-07T10:30:00Z",
        "updated_at": "2026-04-07T14:22:00Z",
        "description": "User reports being unable to login after resetting password via email link.",
        "resolution": None,
    },
    "TK-1002": {
        "ticket_id": "TK-1002",
        "subject": "API returns 500 on user enrollment",
        "status": "in_progress",
        "priority": "critical",
        "category": "api",
        "assigned_to": "support",
        "created_at": "2026-04-06T09:15:00Z",
        "updated_at": "2026-04-07T16:45:00Z",
        "description": "POST /api/v1/enrollments returns HTTP 500 intermittently.",
        "resolution": None,
    },
    "TK-1003": {
        "ticket_id": "TK-1003",
        "subject": "Email notifications not being delivered",
        "status": "resolved",
        "priority": "medium",
        "category": "email",
        "assigned_to": "support",
        "created_at": "2026-04-05T11:00:00Z",
        "updated_at": "2026-04-06T10:30:00Z",
        "description": "Batch emails for course reminders are not reaching recipients.",
        "resolution": "SPF record was missing for the sending domain. Added TXT record and redelivered.",
    },
    "TK-1004": {
        "ticket_id": "TK-1004",
        "subject": "GDPR data export taking too long",
        "status": "escalated",
        "priority": "high",
        "category": "compliance",
        "assigned_to": "escalation",
        "created_at": "2026-04-04T08:00:00Z",
        "updated_at": "2026-04-07T09:00:00Z",
        "description": "Data export for 50k users has been running for 48 hours with no progress.",
        "resolution": None,
    },
}

# ── Classification rules (keyword-based mock) ─────────────────────

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "authentication": ["login", "password", "sso", "saml", "auth", "token", "session", "mfa", "2fa"],
    "api": ["api", "endpoint", "rest", "http", "500", "429", "rate limit", "webhook", "integration"],
    "email": ["email", "smtp", "notification", "delivery", "bounce", "spam"],
    "compliance": ["gdpr", "export", "privacy", "data deletion", "sar", "compliance"],
    "billing": ["invoice", "payment", "subscription", "license", "billing", "plan"],
    "general": [],
}

_PRIORITY_KEYWORDS: dict[str, list[str]] = {
    "critical": ["down", "outage", "500", "crash", "data loss", "security breach", "urgent"],
    "high": ["cannot", "unable", "broken", "failing", "blocked", "not working"],
    "medium": ["slow", "intermittent", "sometimes", "delay", "issue"],
    "low": ["question", "how to", "feature request", "suggestion", "minor"],
}


# ── Public tools ───────────────────────────────────────────────────


def classify_ticket(description: str = "", **kwargs: Any) -> dict[str, Any]:
    """
    Classify a support ticket by priority and category based on its description.

    Parameters
    ----------
    description : str
        The ticket description or user's problem statement.

    Returns
    -------
    dict
        Classification result with priority, category, confidence,
        suggested_agent, and reasoning.
    """
    text = (description or kwargs.get("query", "")).lower()

    if not text:
        return {"error": "No description provided for classification"}

    # Determine category
    category = "general"
    category_score = 0
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw in text)
        if matches > category_score:
            category_score = matches
            category = cat

    # Determine priority
    priority = "medium"
    for prio, keywords in _PRIORITY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            priority = prio
            break

    # Determine suggested agent
    if priority == "critical" or "escalat" in text:
        suggested_agent = "escalation"
    else:
        suggested_agent = "support"

    confidence = min(0.95, 0.6 + category_score * 0.1)

    return {
        "priority": priority,
        "category": category,
        "confidence": round(confidence, 2),
        "suggested_agent": suggested_agent,
        "reasoning": (
            f"Classified as '{category}' (matched {category_score} keyword(s)) "
            f"with '{priority}' priority. Routing to {suggested_agent} agent."
        ),
    }


def get_ticket_status(ticket_id: str = "", **kwargs: Any) -> dict[str, Any]:
    """
    Look up the current status of a support ticket.

    Parameters
    ----------
    ticket_id : str
        The ticket identifier (e.g. "TK-1001").

    Returns
    -------
    dict
        Full ticket details including status, priority, assignment, and resolution.
        Returns an error dict if the ticket is not found.
    """
    tid = (ticket_id or kwargs.get("query", "")).strip().upper()

    if not tid:
        return {"error": "No ticket ID provided"}

    ticket = _TICKETS.get(tid)
    if ticket is None:
        return {
            "error": f"Ticket '{tid}' not found",
            "available_tickets": list(_TICKETS.keys()),
        }

    return {**ticket}


def search_kb(query: str = "", **kwargs: Any) -> dict[str, Any]:
    """
    Search the knowledge base for articles relevant to a query.

    Parameters
    ----------
    query : str
        The search query (matches against titles, content, and tags).

    Returns
    -------
    dict
        Search results with matched articles ranked by relevance score.
    """
    text = (query or kwargs.get("query", "")).lower()

    if not text:
        return {"error": "No search query provided"}

    scored_articles: list[tuple[float, dict[str, Any]]] = []

    for article in _KB_ARTICLES:
        score = 0.0

        # Title match (highest weight)
        title_lower = article["title"].lower()
        for word in text.split():
            if word in title_lower:
                score += 3.0

        # Tag match
        for tag in article["tags"]:
            if tag in text or any(word in tag for word in text.split()):
                score += 2.0

        # Content match
        content_lower = article["content"].lower()
        for word in text.split():
            if len(word) > 2 and word in content_lower:
                score += 1.0

        # Category match
        if article["category"].lower() in text:
            score += 1.5

        if score > 0:
            # Add small random jitter for realism
            score += random.uniform(0, 0.5)
            scored_articles.append((score, article))

    scored_articles.sort(key=lambda x: x[0], reverse=True)
    top_results = scored_articles[:3]

    if not top_results:
        return {
            "query": query,
            "results": [],
            "message": "No matching knowledge base articles found. Consider escalating to a human agent.",
        }

    max_score = top_results[0][0] if top_results else 1.0

    return {
        "query": query,
        "results": [
            {
                "article_id": article["id"],
                "title": article["title"],
                "category": article["category"],
                "content": article["content"],
                "relevance_score": round(score / max_score, 2),
            }
            for score, article in top_results
        ],
        "total_matches": len(scored_articles),
    }
