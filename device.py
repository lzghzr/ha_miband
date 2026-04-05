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
    ),
    0x59FA: DeviceEntry(
        model="M2457B1",
        name="Smart Band 10",
        binary_sensor=[key.value for key in MiBandBinarySensorDeviceClass],
        event=[key.value for key in MiBandEventDeviceClass],
        sensor=[key.value for key in MiBandSensorDeviceClass],
    ),
    0x59FB: DeviceEntry(
        model="M2456B1",
        name="Smart Band 10 NFC",
        binary_sensor=[key.value for key in MiBandBinarySensorDeviceClass],
        event=[key.value for key in MiBandEventDeviceClass],
        sensor=[key.value for key in MiBandSensorDeviceClass],
    ),
    0x59FC: DeviceEntry(
        model="M2456B1",
        name="Smart Band 10 Ceramic Edition",
        binary_sensor=[key.value for key in MiBandBinarySensorDeviceClass],
        event=[key.value for key in MiBandEventDeviceClass],
        sensor=[key.value for key in MiBandSensorDeviceClass],
    ),
    0x6188: DeviceEntry(
        model="M2456B1",
        name="Smart Band 10 Glimmer Edition",
        binary_sensor=[key.value for key in MiBandBinarySensorDeviceClass],
        event=[key.value for key in MiBandEventDeviceClass],
        sensor=[key.value for key in MiBandSensorDeviceClass],
    ),
}


def device_key_to_bluetooth_entity_key(
    device_key: DeviceKey,
) -> PassiveBluetoothEntityKey:
    """Convert a device key to an entity key."""
    return PassiveBluetoothEntityKey(device_key.key, device_key.device_id)
