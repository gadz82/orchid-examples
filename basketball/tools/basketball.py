"""
Built-in tools — NBA basketball stats and roster data (demo).

All data is static / in-memory.  No external API calls.
Functions accept ``**kwargs`` to absorb extra arguments
(``query``, ``context``) that GenericAgent passes automatically.
"""

from __future__ import annotations

from typing import Any

# ── Static player database ──────────────────────────────────────

_PLAYERS: dict[str, dict[str, Any]] = {
    "lebron james": {
        "name": "LeBron James",
        "team": "Los Angeles Lakers",
        "position": "SF",
        "ppg": 25.7,
        "rpg": 7.3,
        "apg": 8.3,
        "age": 41,
        "seasons": 22,
        "championships": 4,
    },
    "stephen curry": {
        "name": "Stephen Curry",
        "team": "Golden State Warriors",
        "position": "PG",
        "ppg": 26.4,
        "rpg": 4.5,
        "apg": 6.5,
        "age": 38,
        "seasons": 16,
        "championships": 4,
    },
    "giannis antetokounmpo": {
        "name": "Giannis Antetokounmpo",
        "team": "Milwaukee Bucks",
        "position": "PF",
        "ppg": 29.9,
        "rpg": 11.5,
        "apg": 5.8,
        "age": 31,
        "seasons": 13,
        "championships": 1,
    },
    "nikola jokic": {
        "name": "Nikola Jokic",
        "team": "Denver Nuggets",
        "position": "C",
        "ppg": 26.4,
        "rpg": 12.4,
        "apg": 9.0,
        "age": 31,
        "seasons": 11,
        "championships": 1,
    },
    "luka doncic": {
        "name": "Luka Doncic",
        "team": "Los Angeles Lakers",
        "position": "PG",
        "ppg": 28.7,
        "rpg": 8.3,
        "apg": 8.0,
        "age": 27,
        "seasons": 8,
        "championships": 0,
    },
    "anthony davis": {
        "name": "Anthony Davis",
        "team": "Los Angeles Lakers",
        "position": "PF/C",
        "ppg": 24.1,
        "rpg": 12.6,
        "apg": 3.5,
        "age": 33,
        "seasons": 14,
        "championships": 1,
    },
    "jayson tatum": {
        "name": "Jayson Tatum",
        "team": "Boston Celtics",
        "position": "SF",
        "ppg": 27.0,
        "rpg": 8.1,
        "apg": 4.6,
        "age": 28,
        "seasons": 9,
        "championships": 1,
    },
    "joel embiid": {
        "name": "Joel Embiid",
        "team": "Philadelphia 76ers",
        "position": "C",
        "ppg": 27.9,
        "rpg": 11.0,
        "apg": 3.6,
        "age": 32,
        "seasons": 10,
        "championships": 0,
    },
    "andrew wiggins": {
        "name": "Andrew Wiggins",
        "team": "Golden State Warriors",
        "position": "SF",
        "ppg": 17.1,
        "rpg": 4.5,
        "apg": 2.2,
        "age": 31,
        "seasons": 12,
        "championships": 1,
    },
    "khris middleton": {
        "name": "Khris Middleton",
        "team": "Milwaukee Bucks",
        "position": "SF",
        "ppg": 19.2,
        "rpg": 5.4,
        "apg": 4.3,
        "age": 34,
        "seasons": 13,
        "championships": 1,
    },
}

# ── Team lookup (derived) ───────────────────────────────────────

_TEAMS: dict[str, list[str]] = {}
for _key, _p in _PLAYERS.items():
    _team_lower = _p["team"].lower()
    _TEAMS.setdefault(_team_lower, []).append(_key)


def _find_player(name: str) -> dict[str, Any] | None:
    """Case-insensitive player lookup with partial matching."""
    key = name.strip().lower()
    if key in _PLAYERS:
        return _PLAYERS[key]
    # Partial match — find first player whose name contains the query
    for player_key, player in _PLAYERS.items():
        if key in player_key:
            return player
    return None


# ── Public tools ────────────────────────────────────────────────


def get_player_stats(player_name: str = "", **kwargs: Any) -> dict[str, Any]:
    """
    Look up an NBA player's stats.

    Parameters
    ----------
    player_name : str
        Full or partial player name (case-insensitive).

    Returns
    -------
    dict
        Player stats including PPG, RPG, APG, team, position, etc.
        Returns an error dict if the player is not found.
    """
    name = player_name or kwargs.get("query", "")
    player = _find_player(name)
    if player is None:
        return {"error": f"Player '{name}' not found", "available": [p["name"] for p in _PLAYERS.values()]}
    return {**player}


def compare_players(player_a: str = "", player_b: str = "", **kwargs: Any) -> dict[str, Any]:
    """
    Compare two NBA players side-by-side.

    Parameters
    ----------
    player_a : str
        First player name.
    player_b : str
        Second player name.

    Returns
    -------
    dict
        Side-by-side stats with advantage analysis per category.
    """
    a = _find_player(player_a)
    b = _find_player(player_b)

    if a is None or b is None:
        missing = []
        if a is None:
            missing.append(player_a)
        if b is None:
            missing.append(player_b)
        return {"error": f"Player(s) not found: {', '.join(missing)}"}

    comparison: dict[str, Any] = {
        "player_a": a,
        "player_b": b,
        "advantages": {},
    }

    for stat in ("ppg", "rpg", "apg"):
        label = {"ppg": "scoring", "rpg": "rebounding", "apg": "assists"}[stat]
        if a[stat] > b[stat]:
            comparison["advantages"][label] = a["name"]
        elif b[stat] > a[stat]:
            comparison["advantages"][label] = b["name"]
        else:
            comparison["advantages"][label] = "tied"

    return comparison


def get_team_roster(team_name: str = "", **kwargs: Any) -> list[dict[str, Any]]:
    """
    Get all players on a given NBA team.

    Parameters
    ----------
    team_name : str
        Full or partial team name (case-insensitive).

    Returns
    -------
    list[dict]
        List of player stat dicts for the team.
        Returns a single error dict in a list if no team matches.
    """
    name = team_name or kwargs.get("query", "")
    key = name.strip().lower()

    # Exact match
    if key in _TEAMS:
        return [_PLAYERS[pk] for pk in _TEAMS[key]]

    # Partial match
    for team_key, player_keys in _TEAMS.items():
        if key in team_key:
            return [_PLAYERS[pk] for pk in player_keys]

    available = sorted({p["team"] for p in _PLAYERS.values()})
    return [{"error": f"Team '{name}' not found", "available_teams": available}]
