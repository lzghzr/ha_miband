"""The MiBand integration."""

from collections.abc import Callable
from logging import Logger

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .parser import XiaomiBluetoothDeviceData, SensorUpdate


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


class MiBandDataProcessor[_T](PassiveBluetoothDataProcessor[_T, SensorUpdate]):
    coordinator: MiBandCoordinator
