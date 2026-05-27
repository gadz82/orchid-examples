from __future__ import annotations

from typing import Any

from orchid_ai.core.tool import OrchidTool, OrchidToolInput, OrchidToolOutput

_VENUES: dict[str, dict[str, Any]] = {
    "main stage": {
        "name": "Main Stage",
        "capacity": 45000,
        "available_slots": 12,
        "power_grid": "400A three-phase with distribution",
        "stage_dimensions": "24m x 18m",
        "backstage_rooms": 8,
        "sound_system": "L-Acoustics K2 line array",
        "lighting_rig": "Full Martin MAC rig with ChamSys console",
    },
    "second stage": {
        "name": "Second Stage",
        "capacity": 12000,
        "available_slots": 18,
        "power_grid": "200A three-phase",
        "stage_dimensions": "16m x 12m",
        "backstage_rooms": 4,
        "sound_system": "d&b audiotechnik J-Series",
        "lighting_rig": "Ayrton Domino + Ghibli hybrid rig",
    },
    "electronic tent": {
        "name": "Electronic Tent",
        "capacity": 6000,
        "available_slots": 24,
        "power_grid": "125A three-phase",
        "stage_dimensions": "10m x 8m",
        "backstage_rooms": 2,
        "sound_system": "Funktion-One Vero VX system",
        "lighting_rig": "LED wall + Chauvet Maverick moving heads",
    },
    "acoustic garden": {
        "name": "Acoustic Garden",
        "capacity": 1500,
        "available_slots": 30,
        "power_grid": "63A single-phase",
        "stage_dimensions": "6m x 5m",
        "backstage_rooms": 1,
        "sound_system": "Meyer Sound UPA + 600HP subs",
        "lighting_rig": "Warm white COB LED pars only",
    },
    "late night arena": {
        "name": "Late Night Arena",
        "capacity": 3000,
        "available_slots": 16,
        "power_grid": "160A three-phase with UPS backup",
        "stage_dimensions": "12m x 10m",
        "backstage_rooms": 2,
        "sound_system": "Void Acoustics Air Motion system",
        "lighting_rig": "Full laser rig + UV + haze (dedicated hazers)",
    },
}


def _tool_kwargs(tool_input: OrchidToolInput) -> dict[str, Any]:
    kwargs = dict(tool_input.parameters)
    kwargs.setdefault("query", tool_input.query)
    kwargs.setdefault("context", tool_input.context)
    kwargs.setdefault("auth_context", tool_input.auth_context)
    kwargs.setdefault("content_sources", tool_input.content_sources)
    return kwargs

_SCHEDULE_SLOTS: dict[str, dict[str, Any]] = {
    "friday 18:00": {"stage": "main stage", "confirmed": None, "status": "open"},
    "friday 20:00": {"stage": "main stage", "confirmed": None, "status": "open"},
    "friday 22:00": {"stage": "main stage", "confirmed": "aurora flux", "status": "confirmed"},
    "saturday 18:00": {"stage": "main stage", "confirmed": None, "status": "open"},
    "saturday 20:00": {"stage": "main stage", "confirmed": "solar eclipse collective", "status": "confirmed"},
    "saturday 22:00": {"stage": "main stage", "confirmed": None, "status": "open"},
    "friday 17:00": {"stage": "electronic tent", "confirmed": None, "status": "open"},
    "friday 23:00": {"stage": "electronic tent", "confirmed": "dj kaleidoscope", "status": "confirmed"},
    "saturday 15:00": {"stage": "acoustic garden", "confirmed": "luna & the tides", "status": "confirmed"},
    "saturday 19:00": {"stage": "second stage", "confirmed": "neon cathedral", "status": "confirmed"},
}


def check_venue_availability(stage_name: str = "", **kwargs: Any) -> dict[str, Any]:
    stage_key = stage_name.lower().strip()
    if stage_key not in _VENUES:
        return {"error": f"Venue '{stage_name}' not found", "available_venues": list(_VENUES)}
    venue = _VENUES[stage_key]
    return {
        "venue": venue,
        "open_slots": [
            k for k, v in _SCHEDULE_SLOTS.items() if v["stage"] == stage_key and v["status"] == "open"
        ],
    }


def get_schedule_overview(**kwargs: Any) -> dict[str, Any]:
    confirmed = {k: v for k, v in _SCHEDULE_SLOTS.items() if v["status"] == "confirmed"}
    open_slots = {k: v for k, v in _SCHEDULE_SLOTS.items() if v["status"] == "open"}
    return {
        "confirmed_bookings": len(confirmed),
        "open_slots": len(open_slots),
        "confirmed_details": {
            slot: {
                "stage": v["stage"],
                "artist": v["confirmed"],
            }
            for slot, v in confirmed.items()
        },
        "stages": {name: {"capacity": d["capacity"], "open_slots": d["available_slots"]} for name, d in _VENUES.items()},
    }


def estimate_power_budget(stage_name: str = "", **kwargs: Any) -> dict[str, Any]:
    stage_key = stage_name.lower().strip()
    if stage_key not in _VENUES:
        return {"error": f"Venue '{stage_name}' not found"}

    booked_artists = []
    for slot_info in _SCHEDULE_SLOTS.values():
        if slot_info["stage"] == stage_key and slot_info["confirmed"]:
            booked_artists.append(slot_info["confirmed"])

    venue = _VENUES[stage_key]
    return {
        "venue_power_grid": venue["power_grid"],
        "booked_artists": booked_artists,
        "note": "Individual artist power requirements available via get_rider_details on the artist booking agent",
    }


def get_crew_requirements(stage_count: int = 0, **kwargs: Any) -> dict[str, Any]:
    return {
        "crew_estimates": {
            "sound_engineers": stage_count * 2,
            "lighting_techs": stage_count * 2,
            "stage_hands": stage_count * 4,
            "runner_team": 6,
            "security_per_stage": stage_count * 8,
            "medical_team": 4 if stage_count > 2 else 2,
        },
        "note": "Estimates assume medium-production festival. Scale up for headline acts with complex riders.",
    }


class CheckVenueAvailabilityTool(OrchidTool):
    name = "check_venue_availability"
    description = "Check venue availability: capacity, open slots, power grid specs"
    parameters_schema = {
        "type": "object",
        "properties": {
            "stage_name": {
                "type": "string",
                "description": "Stage name (e.g. 'main stage')",
                "default": "",
            },
        },
    }

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        return OrchidToolOutput(result=check_venue_availability(**_tool_kwargs(tool_input)))


class GetScheduleOverviewTool(OrchidTool):
    name = "get_schedule_overview"
    description = "Get full schedule overview: confirmed bookings and open slots across all stages"
    parameters_schema = {"type": "object", "properties": {}}

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        return OrchidToolOutput(result=get_schedule_overview(**_tool_kwargs(tool_input)))


class EstimatePowerBudgetTool(OrchidTool):
    name = "estimate_power_budget"
    description = "Estimate power budget for a stage based on confirmed artists"
    parameters_schema = {
        "type": "object",
        "properties": {
            "stage_name": {
                "type": "string",
                "description": "Stage name",
                "default": "",
            },
        },
    }

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        return OrchidToolOutput(result=estimate_power_budget(**_tool_kwargs(tool_input)))


class GetCrewRequirementsTool(OrchidTool):
    name = "get_crew_requirements"
    description = "Estimate crew needs: sound engineers, lighting techs, security, medical"
    parameters_schema = {
        "type": "object",
        "properties": {
            "stage_count": {
                "type": "integer",
                "description": "Number of active stages",
                "default": 0,
            },
        },
    }

    async def invoke(self, tool_input: OrchidToolInput) -> OrchidToolOutput:
        return OrchidToolOutput(result=get_crew_requirements(**_tool_kwargs(tool_input)))
