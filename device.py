"""Support for MiBand devices."""

import dataclasses

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothEntityKey,
)

from .const import (
    MANUFACTURER,
    MiBandBinarySensorDeviceClass,
    MiBandEventDeviceClass,
    MiBandSensorDeviceClass,
)
from .parser import DeviceKey


@dataclasses.dataclass(frozen=True)
class DeviceEntry:
    model: str
    name: str
    manufacturer: str = MANUFACTURER
    binary_sensor: list = dataclasses.field(default_factory=list)
    event: list = dataclasses.field(default_factory=list)
    sensor: list = dataclasses.field(default_factory=list)


DEVICE_TYPES: dict[int, DeviceEntry] = {
    0x0: DeviceEntry(
        model="Unknown",
        name="Unknown",
        binary_sensor=[],
        event=[],
        sensor=[],
    ),
    0x3916: DeviceEntry(
        model="mijia.watch.n62",
        name="Xiaomi Watch S3",
        binary_sensor=[
            MiBandBinarySensorDeviceClass.SLEEP,
            MiBandBinarySensorDeviceClass.WEARING,
        ],
        event=[
            MiBandEventDeviceClass.ABNORMAL_SIGNS,
            MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
            MiBandEventDeviceClass.SPORTS,
        ],
        sensor=[MiBandSensorDeviceClass.BATTERY_CHARGING],
    ),
    0x398C: DeviceEntry(
        model="mijia.watch.n62lte",
        name="Xiaomi Watch S3 eSIM",
        binary_sensor=[
            MiBandBinarySensorDeviceClass.SLEEP,
            MiBandBinarySensorDeviceClass.WEARING,
        ],
        event=[
            MiBandEventDeviceClass.ABNORMAL_SIGNS,
            MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
            MiBandEventDeviceClass.SPORTS,
        ],
        sensor=[MiBandSensorDeviceClass.BATTERY_CHARGING],
    ),
    0x39C8: DeviceEntry(
        model="mijia.watch.n62s",
        name="Xiaomi Watch S4 Sport",
        binary_sensor=[
            MiBandBinarySensorDeviceClass.SLEEP,
            MiBandBinarySensorDeviceClass.WEARING,
        ],
        event=[
            MiBandEventDeviceClass.ABNORMAL_SIGNS,
            MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
            MiBandEventDeviceClass.SPORTS,
        ],
        sensor=[MiBandSensorDeviceClass.BATTERY_CHARGING],
    ),
    0x4461: DeviceEntry(
        model="mijia.watch.n62car",
        name="Xiaomi Watch S3 eSIM",
        binary_sensor=[
            MiBandBinarySensorDeviceClass.SLEEP,
            MiBandBinarySensorDeviceClass.WEARING,
        ],
        event=[
            MiBandEventDeviceClass.ABNORMAL_SIGNS,
            MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
            MiBandEventDeviceClass.SPORTS,
        ],
        sensor=[MiBandSensorDeviceClass.BATTERY_CHARGING],
    ),
    0x4671: DeviceEntry(
        model="mijia.watch.n62cg",
        name="Xiaomi Watch S3 eSIM",
        binary_sensor=[
            MiBandBinarySensorDeviceClass.SLEEP,
            MiBandBinarySensorDeviceClass.WEARING,
        ],
        event=[
            MiBandEventDeviceClass.ABNORMAL_SIGNS,
            MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
            MiBandEventDeviceClass.SPORTS,
        ],
        sensor=[MiBandSensorDeviceClass.BATTERY_CHARGING],
    ),
    0x4E01: DeviceEntry(
        model="mijia.watch.o62",
        name="Xiaomi Watch S4",
        binary_sensor=[
            MiBandBinarySensorDeviceClass.SLEEP,
            MiBandBinarySensorDeviceClass.WEARING,
        ],
        event=[
            MiBandEventDeviceClass.ABNORMAL_SIGNS,
            MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
            MiBandEventDeviceClass.SPORTS,
        ],
        sensor=[MiBandSensorDeviceClass.BATTERY_CHARGING],
    ),
    0x4E02: DeviceEntry(
        model="mijia.watch.o62lte",
        name="Xiaomi Watch S4 eSIM",
        binary_sensor=[
            MiBandBinarySensorDeviceClass.SLEEP,
            MiBandBinarySensorDeviceClass.WEARING,
        ],
        event=[
            MiBandEventDeviceClass.ABNORMAL_SIGNS,
            MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
            MiBandEventDeviceClass.SPORTS,
        ],
        sensor=[MiBandSensorDeviceClass.BATTERY_CHARGING],
    ),
    0x4E03: DeviceEntry(
        model="mijia.watch.o62m",
        name="Xiaomi Watch S4 eSIM",
        binary_sensor=[
            MiBandBinarySensorDeviceClass.SLEEP,
            MiBandBinarySensorDeviceClass.WEARING,
        ],
        event=[
            MiBandEventDeviceClass.ABNORMAL_SIGNS,
            MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
            MiBandEventDeviceClass.SPORTS,
        ],
        sensor=[MiBandSensorDeviceClass.BATTERY_CHARGING],
    ),
    0x4F2A: DeviceEntry(
        model="miwear.watch.o65",
        name="REDMI Watch 5",
        binary_sensor=[
            MiBandBinarySensorDeviceClass.SLEEP,
            MiBandBinarySensorDeviceClass.WEARING,
        ],
        event=[
            MiBandEventDeviceClass.ABNORMAL_SIGNS,
            MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
            MiBandEventDeviceClass.SPORTS,
        ],
        sensor=[MiBandSensorDeviceClass.BATTERY_CHARGING],
    ),
    0x4F2B: DeviceEntry(
        model="miwear.watch.o65m",
        name="REDMI Watch 5 eSIM",
        binary_sensor=[
            MiBandBinarySensorDeviceClass.SLEEP,
            MiBandBinarySensorDeviceClass.WEARING,
        ],
        event=[
            MiBandEventDeviceClass.ABNORMAL_SIGNS,
            MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
            MiBandEventDeviceClass.SPORTS,
        ],
        sensor=[MiBandSensorDeviceClass.BATTERY_CHARGING],
    ),
    0x5736: DeviceEntry(
        model="miwear.watch.o61",
        name="Xiaomi Watch 5",
        binary_sensor=[
            MiBandBinarySensorDeviceClass.SLEEP,
            MiBandBinarySensorDeviceClass.WEARING,
        ],
        event=[
            MiBandEventDeviceClass.ABNORMAL_SIGNS,
            MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
            MiBandEventDeviceClass.SPORTS,
        ],
        sensor=[MiBandSensorDeviceClass.BATTERY_CHARGING],
    ),
    0x578A: DeviceEntry(
        model="miwear.watch.o61lte",
        name="Xiaomi Watch 5 eSIM",
        binary_sensor=[
            MiBandBinarySensorDeviceClass.SLEEP,
            MiBandBinarySensorDeviceClass.WEARING,
        ],
        event=[
            MiBandEventDeviceClass.ABNORMAL_SIGNS,
            MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
            MiBandEventDeviceClass.SPORTS,
        ],
        sensor=[MiBandSensorDeviceClass.BATTERY_CHARGING],
    ),
    0x59FA: DeviceEntry(
        model="miwear.watch.o66cn",
        name="Smart Band 10",
        binary_sensor=[
            MiBandBinarySensorDeviceClass.SLEEP,
            MiBandBinarySensorDeviceClass.WEARING,
        ],
        event=[
            MiBandEventDeviceClass.ABNORMAL_SIGNS,
            MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
            MiBandEventDeviceClass.SPORTS,
        ],
        sensor=[MiBandSensorDeviceClass.BATTERY_CHARGING],
    ),
    0x59FB: DeviceEntry(
        model="miwear.watch.o66nfc",
        name="Smart Band 10 NFC",
        binary_sensor=[
            MiBandBinarySensorDeviceClass.SLEEP,
            MiBandBinarySensorDeviceClass.WEARING,
        ],
        event=[
            MiBandEventDeviceClass.ABNORMAL_SIGNS,
            MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
            MiBandEventDeviceClass.SPORTS,
        ],
        sensor=[MiBandSensorDeviceClass.BATTERY_CHARGING],
    ),
    0x59FC: DeviceEntry(
        model="miwear.watch.o66tc",
        name="Smart Band 10 Ceramic Edition",
        binary_sensor=[
            MiBandBinarySensorDeviceClass.SLEEP,
            MiBandBinarySensorDeviceClass.WEARING,
        ],
        event=[
            MiBandEventDeviceClass.ABNORMAL_SIGNS,
            MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
            MiBandEventDeviceClass.SPORTS,
        ],
        sensor=[MiBandSensorDeviceClass.BATTERY_CHARGING],
    ),
    0x5F5E: DeviceEntry(
        model="miwear.watch.o63",
        name="Xiaomi Watch S4 41mm",
        binary_sensor=[
            MiBandBinarySensorDeviceClass.SLEEP,
            MiBandBinarySensorDeviceClass.WEARING,
        ],
        event=[
            MiBandEventDeviceClass.ABNORMAL_SIGNS,
            MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
            MiBandEventDeviceClass.SPORTS,
        ],
        sensor=[MiBandSensorDeviceClass.BATTERY_CHARGING],
    ),
    0x6188: DeviceEntry(
        model="miwear.watch.o66lj",
        name="Smart Band 10 Glimmer Edition",
        binary_sensor=[
            MiBandBinarySensorDeviceClass.SLEEP,
            MiBandBinarySensorDeviceClass.WEARING,
        ],
        event=[
            MiBandEventDeviceClass.ABNORMAL_SIGNS,
            MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
            MiBandEventDeviceClass.SPORTS,
        ],
        sensor=[MiBandSensorDeviceClass.BATTERY_CHARGING],
    ),
    0x67CC: DeviceEntry(
        model="miwear.watch.p65",
        name="REDMI Watch 6",
        binary_sensor=[
            MiBandBinarySensorDeviceClass.SLEEP,
            MiBandBinarySensorDeviceClass.WEARING,
        ],
        event=[
            MiBandEventDeviceClass.ABNORMAL_SIGNS,
            MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
            MiBandEventDeviceClass.SPORTS,
        ],
        sensor=[MiBandSensorDeviceClass.BATTERY_CHARGING],
    ),
}


def device_key_to_bluetooth_entity_key(
    device_key: DeviceKey,
) -> PassiveBluetoothEntityKey:
    """Convert a device key to an entity key."""
    return PassiveBluetoothEntityKey(device_key.key, device_key.device_id)
