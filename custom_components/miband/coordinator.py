"""The MiBand integration."""

from collections.abc import Callable
from logging import Logger

from bluetooth_data_tools import short_address
from sensor_state_data import (
    BinarySensorDescription,
    DeviceKey,
    SensorDescription,
    SensorDeviceInfo,
    SensorUpdate,
)

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .device import DeviceEntry
from .parser import XiaomiBluetoothDeviceData

type MiBandConfigEntry = ConfigEntry[MiBandCoordinator]


class MiBandCoordinator(PassiveBluetoothProcessorCoordinator[SensorUpdate]):
    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        address: str,
        update_method: Callable[[BluetoothServiceInfoBleak], SensorUpdate],
        device_data: XiaomiBluetoothDeviceData,
        entry: MiBandConfigEntry,
    ) -> None:
        super().__init__(
            hass, logger, address, BluetoothScanningMode.PASSIVE, update_method
        )
        self.device_data = device_data
        self.entry = entry
        self.registered_event_classes: set[str] = set()

    @callback
    def async_seed_entities(self, device: DeviceEntry) -> None:
        """Publish this model's descriptions without a reading or an advertisement."""
        descriptions = SensorUpdate(
            title=None,
            devices={
                None: SensorDeviceInfo(
                    name=f"{device.name} {short_address(self.address)}",
                    model=device.model,
                    manufacturer=device.manufacturer,
                    sw_version=None,
                    hw_version=None,
                )
            },
            binary_entity_descriptions={
                (key := DeviceKey(kind, None)): BinarySensorDescription(
                    device_key=key, device_class=kind
                )
                for kind in device.binary_sensor
            },
            entity_descriptions={
                (key := DeviceKey(kind, None)): SensorDescription(
                    device_key=key, device_class=kind, native_unit_of_measurement=None
                )
                for kind in device.sensor
            },
        )
        self._process_update(descriptions)


class MiBandDataProcessor[_T](PassiveBluetoothDataProcessor[_T, SensorUpdate]):
    coordinator: MiBandCoordinator
