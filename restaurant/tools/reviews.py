"""
Built-in tools — customer review sentiment analysis.

All data is static / in-memory.  No external API calls.
Functions accept ``**kwargs`` to absorb extra arguments
(``query``, ``context``) that GenericAgent passes automatically.
"""

from __future__ import annotations

from typing import Any

# -- Simple keyword-based sentiment scoring (mock) --------------------------

_POSITIVE_WORDS = {
    "excellent", "amazing", "fantastic", "delicious", "wonderful", "outstanding",
    "great", "perfect", "love", "loved", "best", "superb", "incredible",
    "fresh", "flavorful", "crispy", "tender", "beautiful", "attentive",
    "friendly", "prompt", "cozy", "recommend", "worth",
}

_NEGATIVE_WORDS = {
    "terrible", "awful", "horrible", "disgusting", "worst", "bad", "cold",
    "stale", "overcooked", "undercooked", "slow", "rude", "expensive",
    "disappointing", "bland", "tasteless", "greasy", "wait", "waited",
    "dirty", "noisy", "overpriced", "raw", "burnt", "soggy",
}


def analyze_sentiment(text: str = "", **kwargs: Any) -> dict[str, Any]:
    """
    Analyze the sentiment of a customer review.

    Parameters
    ----------
    text : str
        The review text to analyze.

    Returns
    -------
    dict
        Sentiment analysis with score (-1.0 to 1.0), keywords found,
        overall rating (1-5 stars), and categorized feedback.
    """
    if not text:
        return {"error": "No review text provided. Please supply the review text."}

    words = set(text.lower().split())
    # Strip basic punctuation from words for matching
    cleaned = {w.strip(".,!?;:'\"()") for w in words}

    pos_found = cleaned & _POSITIVE_WORDS
    neg_found = cleaned & _NEGATIVE_WORDS

    pos_count = len(pos_found)
    neg_count = len(neg_found)
    total = pos_count + neg_count

    if total == 0:
        score = 0.0
        sentiment = "neutral"
        stars = 3
    else:
        score = round((pos_count - neg_count) / total, 2)
        if score > 0.3:
            sentiment = "positive"
            stars = 5 if score > 0.7 else 4
        elif score < -0.3:
            sentiment = "negative"
            stars = 1 if score < -0.7 else 2
        else:
            sentiment = "mixed"
            stars = 3

    # Categorize feedback
    categories = []
    food_words = {"delicious", "fresh", "flavorful", "crispy", "tender", "bland",
                  "tasteless", "greasy", "overcooked", "undercooked", "cold", "stale",
                  "raw", "burnt", "soggy"}
    service_words = {"attentive", "friendly", "prompt", "rude", "slow", "waited", "wait"}
    ambiance_words = {"cozy", "beautiful", "dirty", "noisy"}
    value_words = {"expensive", "overpriced", "worth"}

    if cleaned & food_words:
        categories.append("food_quality")
    if cleaned & service_words:
        categories.append("service")
    if cleaned & ambiance_words:
        categories.append("ambiance")
    if cleaned & value_words:
        categories.append("value")

    return {
        "sentiment": sentiment,
        "score": score,
        "stars": stars,
        "positive_keywords": sorted(pos_found),
        "negative_keywords": sorted(neg_found),
        "categories": categories or ["general"],
        "word_count": len(words),
        "summary": f"{sentiment.capitalize()} review ({stars}/5 stars). "
                   f"Found {pos_count} positive and {neg_count} negative indicators.",
    }
