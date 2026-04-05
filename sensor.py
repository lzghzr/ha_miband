"""Support for Miband sensors."""

from typing import cast

from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    EntityDescription,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info

from .const import BATTERY_CHARGING_STATE, MiBandSensorDeviceClass
from .coordinator import MiBandConfigEntry, MiBandDataProcessor
from .device import device_key_to_bluetooth_entity_key
from .parser import SensorUpdate

SENSOR_DESCRIPTIONS = {
    (
        SensorDeviceClass.SIGNAL_STRENGTH,
        SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ): SensorEntityDescription(
        key=f"{SensorDeviceClass.SIGNAL_STRENGTH}_{SIGNAL_STRENGTH_DECIBELS_MILLIWATT}",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (MiBandSensorDeviceClass.BATTERY_CHARGING, None): SensorEntityDescription(
        key=MiBandSensorDeviceClass.BATTERY_CHARGING,
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:battery-charging",
        options=list(BATTERY_CHARGING_STATE.values()),
        translation_key=MiBandSensorDeviceClass.BATTERY_CHARGING,
    ),
}


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate[float | None]:
    """Convert a sensor update to a bluetooth data update."""
    entity_descriptions: dict[PassiveBluetoothEntityKey, EntityDescription] = {
        device_key_to_bluetooth_entity_key(device_key): SENSOR_DESCRIPTIONS[
            (description.device_class, description.native_unit_of_measurement)
        ]
        for device_key, description in sensor_update.entity_descriptions.items()
        if description.device_class
    }

    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass_device_info(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions=entity_descriptions,
        entity_data={
            device_key_to_bluetooth_entity_key(device_key): cast(
                float | None, sensor_values.native_value
            )
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
        entity_names={
            device_key_to_bluetooth_entity_key(device_key): sensor_values.name
            for device_key, sensor_values in sensor_update.entity_values.items()
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
    """Set up the MiBand sensors."""
    coordinator = entry.runtime_data
    processor = MiBandDataProcessor(sensor_update_to_bluetooth_data_update)

    pd_id = entry.data.get("pd_id")
    coordinator.device_data.add_entities(pd_id)
    entry.async_on_unload(
        processor.async_add_entities_listener(MiBandSensorEntity, async_add_entities)
    )
    entry.async_on_unload(
        coordinator.async_register_processor(processor, SensorEntityDescription)
    )


class MiBandSensorEntity(
    PassiveBluetoothProcessorEntity[MiBandDataProcessor[float | None]],
    SensorEntity,
):
    """Representation of a MiBand sensor."""

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)

    @property
    def available(self) -> bool:
        return True
