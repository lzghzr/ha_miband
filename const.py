"""Constants for the MiBand integration."""

from enum import StrEnum
from typing import Final, TypedDict

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
    256: "other",
}
HAND_GESTURE_TYPE: Final = {
    0: "shake_wrist",
    1: "wrists_outward_and_inward",
    2: "snap_fingers",
    256: "other",
}
MODE_TYPE: Final = {
    0: "mute_on",
    1: "mute_off",
    2: "no_disturb_on",
    3: "no_disturb_off",
    256: "other",
}
SPORT_EVENT_TYPE: Final = {
    0: "sport_start",
    1: "sport_end",
    2: "sport_pause",
    3: "sport_continue",
    256: "other",
}
SPORT_TYPE: Final = {
    1: "run_outdoor",
    2: "walk_outdoor",
    3: "run_indoor",
    4: "climbing",
    5: "cross_country",
    6: "ride_outdoor",
    7: "ride_indoor",
    8: "free_training",
    9: "swim_indoor",
    10: "swim_outdoor",
    11: "elliptical_machine",
    12: "yoga",
    13: "rowing_machine",
    14: "rope_skipping",
    15: "hiking_outdoor",
    16: "high_interval_training",
    100: "sailboat",
    101: "paddle_board",
    102: "water_polo",
    103: "aquatic_sport",
    104: "surfing",
    105: "canoeing",
    106: "kayak_rafting",
    107: "rowing",
    108: "motorboat",
    109: "web_swimming",
    110: "driving",
    111: "fancy_swimming",
    112: "snorkeling",
    113: "kite_surfing",
    114: "indoor_surfing",
    115: "dragon_boat",
    200: "rock_climbing",
    201: "skate",
    202: "roller_skating",
    203: "parkour",
    204: "atv",
    205: "paraglider",
    206: "bicycle_moto",
    207: "hell_and_toe",
    300: "climbing_machine",
    301: "climb_stairs",
    302: "stepper",
    303: "core_training",
    304: "flexibility_training",
    305: "pilates",
    306: "gymnastics",
    307: "stretch",
    308: "strength_training",
    309: "cross_fit",
    310: "aerobics",
    311: "physical_training",
    312: "wall_ball",
    313: "dumbbell_training",
    314: "barbell_training",
    315: "weightlifting",
    316: "deadlift",
    317: "bobby_jump",
    318: "sit_ups",
    319: "functional_training",
    320: "upper_limb_training",
    321: "lower_limb_training",
    322: "waist_training",
    323: "back_training",
    324: "spinning",
    325: "walking_machine",
    326: "step_training",
    327: "single_bar",
    328: "parallel_bars",
    329: "group_callisthenics",
    330: "strike",
    331: "battle_rope",
    332: "mixed_aerobic",
    333: "walk_indoor",
    399: "indoor_gym",
    400: "square_dance",
    401: "belly_dance",
    402: "ballet",
    403: "street_dance",
    404: "zumba",
    405: "national_dance",
    406: "jazz",
    407: "latin_dance",
    408: "hip_hop_dance",
    409: "pole_dance",
    410: "breakdancing",
    411: "social_dancing",
    412: "modern_dancing",
    499: "dance",
    500: "boxing",
    501: "wrestling",
    502: "martial_arts",
    503: "taichi",
    504: "muay_thai",
    505: "judo",
    506: "taekwondo",
    507: "karate",
    508: "free_sparring",
    509: "swordsmanship",
    510: "fencing",
    511: "jujitsu",
    600: "football",
    601: "basketball",
    602: "volleyball",
    603: "baseball",
    604: "softball",
    605: "rugby",
    606: "hockey",
    607: "pingpong",
    608: "badminton",
    609: "tennis",
    610: "cricket",
    611: "handball",
    612: "bowling",
    613: "squash",
    614: "billiards",
    615: "shuttlecock",
    616: "beach_football",
    617: "beach_volleyball",
    618: "sepak_takraw",
    619: "golf",
    620: "foosball",
    621: "indoor_football",
    622: "sandbags_ball",
    623: "bocci",
    624: "hihi_ball",
    625: "gateball",
    626: "dodgeball",
    627: "shuffle_ball",
    700: "outdoor_skating",
    701: "curling",
    702: "snow_sports",
    703: "snowmobile",
    704: "puck",
    705: "snow_car",
    706: "sled",
    707: "indoor_skating",
    708: "snowboarding",
    709: "double_board_skiing",
    710: "cross_country_skiing",
    800: "archery",
    801: "darts",
    802: "horse_riding",
    803: "tug_of_war",
    804: "hula_hoop",
    805: "fly_kite",
    806: "fishing",
    807: "frisbee",
    808: "shuttlecock_kicking",
    809: "swing",
    810: "motion_sensing_game",
    811: "electronic_sports",
    900: "chess",
    901: "draughts",
    902: "weiqi",
    903: "bridge",
    904: "board_games",
    10000: "equesttrian",
    10001: "track_and_field",
    10002: "racing_car",
}
VITALITY_GOAL_TYPE: Final = {
    0: "all_goals_hit",
    1: "step_goal_hit",
    2: "calorie_goal_hit",
    3: "moving_goal_hit",
    4: "standing_goal_hit",
    256: "other",
}

BATTERY_CHARGING_STATE: Final = {
    0: "charging",
    1: "charging_disconnected",
    2: "charging_complete",
    256: "other",
}


class MiBandBinarySensorDeviceClass(StrEnum):
    MUTE = "mute"
    NODISTURB = "no_disturb"
    SLEEP = "sleep"
    WEARING = "wearing"


class MiBandSensorDeviceClass(StrEnum):
    BATTERY_CHARGING = "battery_charging"


class MiBandEventDeviceClass(StrEnum):
    ABNORMAL_SIGNS = "abnormal_signs"
    DAILY_VITALITY_INDEX = "daily_vitality_index"
    MODE = "mode"
    HAND_GESTURE = "hand_gesture"
    SPORTS = "sports"


class MiBandEvent(TypedDict):
    device_id: str
    address: str
    event_class: str
    event_type: str
    translation_key: str | None
    event_properties: dict[str, str | int | float | None] | None
