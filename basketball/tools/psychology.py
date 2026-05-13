"""
Built-in tools — sports psychology assessments (demo).

All logic is rule-based / deterministic.  No external API calls.
Functions accept ``**kwargs`` to absorb extra arguments
(``query``, ``context``) that GenericAgent passes automatically.
"""

from __future__ import annotations

from typing import Any

# ── Motivation profiles (keyed by lowercase player name) ────────

_MOTIVATION_PROFILES: dict[str, dict[str, Any]] = {
    "lebron james": {
        "drive": "legacy",
        "resilience": 9,
        "pressure_response": "thrives",
        "leadership_style": "vocal leader",
        "risk_factors": ["age-related fatigue", "media scrutiny"],
    },
    "stephen curry": {
        "drive": "mastery",
        "resilience": 9,
        "pressure_response": "thrives",
        "leadership_style": "lead by example",
        "risk_factors": ["injury history", "over-reliance on shooting"],
    },
    "giannis antetokounmpo": {
        "drive": "growth",
        "resilience": 10,
        "pressure_response": "channels into intensity",
        "leadership_style": "relentless competitor",
        "risk_factors": ["free-throw anxiety", "carries too much load"],
    },
    "nikola jokic": {
        "drive": "intrinsic joy",
        "resilience": 8,
        "pressure_response": "stays calm",
        "leadership_style": "quiet orchestrator",
        "risk_factors": ["perceived lack of intensity", "conditioning concerns"],
    },
    "luka doncic": {
        "drive": "competitive fire",
        "resilience": 7,
        "pressure_response": "emotional but effective",
        "leadership_style": "ball-dominant creator",
        "risk_factors": ["frustration with referees", "conditioning", "body language"],
    },
    "joel embiid": {
        "drive": "proving doubters wrong",
        "resilience": 7,
        "pressure_response": "inconsistent under high pressure",
        "leadership_style": "emotional catalyst",
        "risk_factors": ["injury anxiety", "inconsistent effort on defense"],
    },
    "jayson tatum": {
        "drive": "championship validation",
        "resilience": 8,
        "pressure_response": "rising to big moments",
        "leadership_style": "steady two-way anchor",
        "risk_factors": ["shot selection in clutch", "passive stretches"],
    },
}

# ── Team dynamics profiles ──────────────────────────────────────

_TEAM_DYNAMICS: dict[str, dict[str, Any]] = {
    "los angeles lakers": {
        "cohesion_score": 7.5,
        "strengths": ["veteran leadership", "star power", "playoff experience"],
        "risks": ["age of core", "ego management", "injury load"],
        "recommendations": [
            "Manage minutes for veteran stars",
            "Build chemistry with structured team bonding",
            "Use mentorship programs for younger players",
        ],
    },
    "golden state warriors": {
        "cohesion_score": 8.5,
        "strengths": ["championship culture", "unselfish play", "system continuity"],
        "risks": ["aging core", "succession planning", "complacency"],
        "recommendations": [
            "Maintain competitive edge through internal scrimmages",
            "Integrate younger players into the system gradually",
            "Celebrate small wins to keep motivation high",
        ],
    },
    "milwaukee bucks": {
        "cohesion_score": 8.0,
        "strengths": ["Giannis's relentless energy", "defensive identity", "trust in system"],
        "risks": ["over-dependence on Giannis", "supporting cast confidence", "fatigue"],
        "recommendations": [
            "Empower secondary scorers with plays designed for them",
            "Scheduled rest for Giannis to preserve peak performance",
            "Team visualization exercises before big games",
        ],
    },
    "denver nuggets": {
        "cohesion_score": 9.0,
        "strengths": ["Jokic's unselfishness elevates everyone", "continuity", "joy of play"],
        "risks": ["external perception of 'boring'", "Murray's durability", "complacency post-chip"],
        "recommendations": [
            "Channel post-championship hunger into daily habits",
            "Create internal competitions to maintain edge",
            "Mental conditioning for playoff pressure",
        ],
    },
    "boston celtics": {
        "cohesion_score": 8.5,
        "strengths": ["defensive versatility", "two-way depth", "championship identity"],
        "risks": ["maintaining hunger after title", "roster turnover", "offensive stagnation"],
        "recommendations": [
            "Set new collective goals beyond repeat",
            "Rotate leadership responsibilities",
            "Invest in mindfulness and recovery routines",
        ],
    },
    "philadelphia 76ers": {
        "cohesion_score": 6.0,
        "strengths": ["Embiid's dominance when healthy", "passionate fanbase"],
        "risks": ["injury uncertainty", "chemistry disruptions", "trust issues from roster changes"],
        "recommendations": [
            "Build psychological safety within the locker room",
            "Develop contingency plans so players feel secure",
            "Focus on communication and conflict resolution",
        ],
    },
}

# ── Mental strategy library ─────────────────────────────────────

_STRATEGIES: dict[str, dict[str, Any]] = {
    "pre-game anxiety": {
        "strategy_name": "Centering Breath Protocol",
        "techniques": [
            "4-7-8 breathing pattern (inhale 4s, hold 7s, exhale 8s)",
            "Progressive muscle relaxation starting from toes",
            "Positive self-talk cue words: 'ready', 'focused', 'dominant'",
        ],
        "expected_outcome": "Reduced cortisol, improved focus, calmer decision-making",
    },
    "shooting slump": {
        "strategy_name": "Process-Over-Outcome Reframing",
        "techniques": [
            "Focus on shooting mechanics, not results",
            "Visualization of 10 perfect makes before each game",
            "Remove stat tracking for 3 games — focus on form only",
        ],
        "expected_outcome": "Reduced performance anxiety, return to natural shooting rhythm",
    },
    "playoff pressure": {
        "strategy_name": "Pressure-Is-Privilege Mindset",
        "techniques": [
            "Reframe pressure as excitement (arousal reappraisal)",
            "Pre-game routine anchoring — same sequence every game",
            "Focus on controllables: effort, communication, body language",
        ],
        "expected_outcome": "Consistent performance under high stakes, improved clutch execution",
    },
    "team conflict": {
        "strategy_name": "Constructive Confrontation Framework",
        "techniques": [
            "Facilitated team meeting with 'I-statement' rule",
            "Shared goal-setting exercise to realign priorities",
            "One-on-one mediation between conflicting parties",
        ],
        "expected_outcome": "Restored trust, clearer communication, stronger collective identity",
    },
    "injury comeback": {
        "strategy_name": "Graduated Confidence Building",
        "techniques": [
            "Progressive exposure: practice → scrimmage → limited minutes → full rotation",
            "Daily journaling of physical sensations (separate fear from real pain)",
            "Highlight reel of pre-injury dominance to rebuild self-image",
        ],
        "expected_outcome": "Faster psychological recovery, reduced re-injury anxiety",
    },
}


def _find_profile(name: str) -> dict[str, Any] | None:
    """Case-insensitive profile lookup with partial matching."""
    key = name.strip().lower()
    if key in _MOTIVATION_PROFILES:
        return _MOTIVATION_PROFILES[key]
    for profile_key, profile in _MOTIVATION_PROFILES.items():
        if key in profile_key:
            return profile
    return None


def _find_team_dynamics(name: str) -> dict[str, Any] | None:
    """Case-insensitive team dynamics lookup with partial matching."""
    key = name.strip().lower()
    if key in _TEAM_DYNAMICS:
        return _TEAM_DYNAMICS[key]
    for team_key, dynamics in _TEAM_DYNAMICS.items():
        if key in team_key:
            return dynamics
    return None


def _match_strategy(situation: str) -> dict[str, Any]:
    """Find the best matching mental strategy for a situation."""
    key = situation.strip().lower()
    # Exact match
    if key in _STRATEGIES:
        return _STRATEGIES[key]
    # Keyword match
    for strat_key, strat in _STRATEGIES.items():
        if any(word in key for word in strat_key.split()):
            return strat
    # Default
    return _STRATEGIES["pre-game anxiety"]


# ── Public tools ────────────────────────────────────────────────


def assess_motivation(player_name: str = "", situation: str = "", **kwargs: Any) -> dict[str, Any]:
    """
    Assess a player's motivation level and psychological factors.

    Parameters
    ----------
    player_name : str
        Player name (case-insensitive, partial match supported).
    situation : str
        Optional game/season context to factor into the assessment.

    Returns
    -------
    dict
        Motivation level (1-10), drive type, resilience, pressure response,
        risk factors, and tailored recommendations.
    """
    name = player_name or kwargs.get("query", "")
    profile = _find_profile(name)

    if profile is None:
        return {
            "error": f"No motivation profile for '{name}'",
            "available": list(_MOTIVATION_PROFILES.keys()),
        }

    # Compute a motivation score from profile attributes
    base_score = profile["resilience"]
    if profile["pressure_response"] in ("thrives", "channels into intensity"):
        base_score = min(10, base_score + 1)
    if situation and any(risk.lower() in situation.lower() for risk in profile["risk_factors"]):
        base_score = max(1, base_score - 1)

    return {
        "player": name.title(),
        "motivation_level": base_score,
        "drive_type": profile["drive"],
        "resilience": profile["resilience"],
        "pressure_response": profile["pressure_response"],
        "leadership_style": profile["leadership_style"],
        "risk_factors": profile["risk_factors"],
        "recommendations": [
            f"Leverage {profile['drive']} drive in goal-setting conversations",
            f"Monitor: {profile['risk_factors'][0]}" if profile["risk_factors"] else "No major concerns",
            "Schedule regular mental check-ins during high-stress stretches",
        ],
    }


def suggest_mental_strategy(situation: str = "", **kwargs: Any) -> dict[str, Any]:
    """
    Suggest mental performance strategies for a given situation.

    Parameters
    ----------
    situation : str
        Description of the challenge (e.g. "shooting slump", "playoff pressure").

    Returns
    -------
    dict
        Strategy name, list of techniques, and expected outcome.
    """
    sit = situation or kwargs.get("query", "")
    strategy = _match_strategy(sit)

    return {
        "situation": sit,
        **strategy,
    }


def analyze_team_dynamics(team_name: str = "", **kwargs: Any) -> dict[str, Any]:
    """
    Analyze team chemistry and group motivation patterns.

    Parameters
    ----------
    team_name : str
        NBA team name (case-insensitive, partial match supported).

    Returns
    -------
    dict
        Cohesion score, strengths, risks, and recommendations.
    """
    name = team_name or kwargs.get("query", "")
    dynamics = _find_team_dynamics(name)

    if dynamics is None:
        available = sorted(_TEAM_DYNAMICS.keys())
        return {
            "error": f"No dynamics profile for '{name}'",
            "available_teams": available,
        }

    return {
        "team": name.title(),
        **dynamics,
    }
