"""Support for MiBand binary sensors."""

from homeassistant.components.binary_sensor import (
    EntityDescription,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

from .const import MiBandBinarySensorDeviceClass
from .coordinator import MiBandConfigEntry, MiBandDataProcessor
from .device import device_key_to_bluetooth_entity_key
from .parser import SensorUpdate

BINARY_SENSOR_DESCRIPTIONS = {
    MiBandBinarySensorDeviceClass.SLEEP: BinarySensorEntityDescription(
        key=MiBandBinarySensorDeviceClass.SLEEP,
        icon="mdi:sleep",
        translation_key=MiBandBinarySensorDeviceClass.SLEEP,
    ),
    MiBandBinarySensorDeviceClass.WEARING: BinarySensorEntityDescription(
        key=MiBandBinarySensorDeviceClass.WEARING,
        icon="mdi:watch-variant",
        translation_key=MiBandBinarySensorDeviceClass.WEARING,
    ),
}


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate[bool | None]:
    """Convert a sensor update to a bluetooth data update."""
    entity_descriptions: dict[PassiveBluetoothEntityKey, EntityDescription] = {
        device_key_to_bluetooth_entity_key(device_key): BINARY_SENSOR_DESCRIPTIONS[
            description.device_class
        ]
        for device_key, description in sensor_update.binary_entity_descriptions.items()
        if description.device_class
    }

    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass_device_info(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions=entity_descriptions,
        entity_data={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.native_value
            for device_key, sensor_values in sensor_update.binary_entity_values.items()
        },
        entity_names={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.name
            for device_key, sensor_values in sensor_update.binary_entity_values.items()
            # Add names where the entity description has neither a translation_key nor
            # a device_class
            if (
                description := entity_descriptions.get(
                    device_key_to_bluetooth_entity_key(device_key)
                )
            )
            is None
            or (
                description.translation_key is None and description.device_class is None
            )
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MiBandConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Miband sensors."""
    coordinator = entry.runtime_data
    processor = MiBandDataProcessor(sensor_update_to_bluetooth_data_update)

    pd_id = entry.data.get("pd_id")
    coordinator.device_data.add_entities(pd_id)
    entry.async_on_unload(
        processor.async_add_entities_listener(MiBandSensorEntity, async_add_entities)
    )
    entry.async_on_unload(
        coordinator.async_register_processor(processor, BinarySensorEntityDescription)
    )


class MiBandSensorEntity(
    PassiveBluetoothProcessorEntity[MiBandDataProcessor[bool | None]],
    BinarySensorEntity,
):
    """Representation of a Miband binary sensor."""

    @property
    def is_on(self) -> bool | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)

    @property
    def available(self) -> bool:
        return True
