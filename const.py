"""Constants for the MiBand integration."""

from __future__ import annotations

from typing import Final, TypedDict
from enum import StrEnum

DOMAIN = "miband"
MANUFACTURER = "Xiaomi"

SERVICE_MIBEACON = "0000fe95-0000-1000-8000-00805f9b34fb"

EVENT_TYPE: Final = "event_type"
EVENT_PROPERTIES: Final = "event_properties"
MIBAND_EVENT: Final = "miband_event"


ABNORMAL_VITAL_SIGNS_TYPE: Final = {
    0: "fall_down",
    1: "high_heart_rate",
    2: "low_heart_rate",
    3: "low_blood_oxygen",
    4: "high_blood_pressure",
    5: "abnormal_heart_beats",
    256: "unknown",
}
SPORT_EVENT_TYPE: Final = {
    0: "sport_start",
    1: "sport_end",
    2: "sport_pause",
    3: "sport_continue",
    256: "unknown",
}
SPORT_TYPE: Final = {
    1: "outdoor_running",
    2: "walking",
    3: "indoor_running",
    4: "mountaineering",
    6: "outdoor_cycling",
    7: "indoor_cycling",
    8: "free_training",
    9: "pool_swimming",
    10: "open_water_swimming",
    11: "elliptical_machine",
    12: "yoga",
    13: "rowing_machine",
    14: "jump_rope",
    15: "on_foot",
    300: "stair_climbing_machine",
    301: "climb_stairs",
    302: "stepper",
    311: "physical_training",
    313: "dumbbell_training",
    314: "barbell_training",
    324: "spinning_bike",
}
VITALITY_GOAL_TYPE: Final = {
    0: "all_goals_hit",
    1: "step_goal_hit",
    2: "calorie_goal_hit",
    3: "moving_goal_hit",
    4: "standing_goal_hit",
    256: "unknown",
}

BATTERY_CHARGING_STATE: Final = {
    0: "charging",
    1: "charging_disconnected",
    2: "charging_complete",
}


class MiBandBinarySensorDeviceClass(StrEnum):
    SLEEP = "sleep"
    WEARING = "wearing"


class MiBandSensorDeviceClass(StrEnum):
    BATTERY_CHARGING = "battery_charging"


class MiBandEventDeviceClass(StrEnum):
    ABNORMAL_SIGNS = "abnormal_signs"
    DAILY_VITALITY_INDEX = "daily_vitality_index"
    SPORTS = "sports"


class MiBandEvent(TypedDict):
    device_id: str
    address: str
    event_class: str
    event_type: str
    translation_key: str | None
    event_properties: dict[str, str | int | float | None] | None
