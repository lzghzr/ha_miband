"""Support for MiBand event entities."""

from homeassistant.components.event import DOMAIN as EVENT_DOMAIN
from homeassistant.components.event import (
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import format_discovered_event_class, format_event_dispatcher_name
from .const import (
    ABNORMAL_VITAL_SIGNS_TYPE,
    DOMAIN,
    EVENT_PROPERTIES,
    EVENT_TYPE,
    HAND_GESTURE_TYPE,
    MODE_TYPE,
    SPORT_EVENT_TYPE,
    VITALITY_GOAL_TYPE,
    MiBandEvent,
    MiBandEventDeviceClass,
)
from .coordinator import MiBandConfigEntry
from .device import DEVICE_TYPES

EVENT_DESCRIPTIONS = {
    MiBandEventDeviceClass.ABNORMAL_SIGNS: EventEntityDescription(
        key=MiBandEventDeviceClass.ABNORMAL_SIGNS,
        event_types=list(ABNORMAL_VITAL_SIGNS_TYPE.values()),
        translation_key=MiBandEventDeviceClass.ABNORMAL_SIGNS,
    ),
    MiBandEventDeviceClass.DAILY_VITALITY_INDEX: EventEntityDescription(
        key=MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
        event_types=list(VITALITY_GOAL_TYPE.values()),
        translation_key=MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
    ),
    MiBandEventDeviceClass.HAND_GESTURE: EventEntityDescription(
        key=MiBandEventDeviceClass.HAND_GESTURE,
        event_types=list(HAND_GESTURE_TYPE.values()),
        translation_key=MiBandEventDeviceClass.HAND_GESTURE,
    ),
    MiBandEventDeviceClass.MODE: EventEntityDescription(
        key=MiBandEventDeviceClass.MODE,
        event_types=list(MODE_TYPE.values()),
        translation_key=MiBandEventDeviceClass.MODE,
    ),
    MiBandEventDeviceClass.SPORTS: EventEntityDescription(
        key=MiBandEventDeviceClass.SPORTS,
        event_types=list(SPORT_EVENT_TYPE.values()),
        translation_key=MiBandEventDeviceClass.SPORTS,
    ),
}


def _event_unique_id(address: str, event_class: str) -> str:
    return f"{address}_{event_class}"


class MiBandEventEntity(EventEntity):
    """Representation of a MiBand event entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        address: str,
        event_class: str,
        event: MiBandEvent | None,
    ) -> None:
        """Initialise a MiBand event entity."""
        self._update_signal = format_event_dispatcher_name(address, event_class)
        self.entity_description = EVENT_DESCRIPTIONS[event_class]
        # Matches logic in PassiveBluetoothProcessorEntity
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, address)},
            connections={(dr.CONNECTION_BLUETOOTH, address)},
        )
        self._attr_unique_id = _event_unique_id(address, event_class)
        self._initial_event = event

    async def async_added_to_hass(self) -> None:
        """Entity added to hass."""
        await super().async_added_to_hass()
        # Apply the discovery frame after HA restores the previous event state.
        if (event := self._initial_event) is not None:
            self._trigger_event(event[EVENT_TYPE], event[EVENT_PROPERTIES])
            self._initial_event = None
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self._update_signal,
                self._async_handle_event,
            )
        )

    @callback
    def _async_handle_event(self, event: MiBandEvent) -> None:
        self._trigger_event(event[EVENT_TYPE], event[EVENT_PROPERTIES])
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MiBandConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up MiBand event."""
    coordinator = entry.runtime_data
    address = coordinator.address

    device = DEVICE_TYPES[entry.data.get("pd_id")]
    registry = er.async_get(hass)
    initial_classes = [
        key
        for key in EVENT_DESCRIPTIONS
        if key in device.event
        or registry.async_get_entity_id(
            EVENT_DOMAIN, DOMAIN, _event_unique_id(address, key)
        )
    ]
    coordinator.registered_event_classes.update(initial_classes)
    async_add_entities(MiBandEventEntity(address, key, None) for key in initial_classes)

    @callback
    def _async_discovered_event_class(event_class: str, event: MiBandEvent) -> None:
        """Create the entity with the event that discovered it."""
        async_add_entities([MiBandEventEntity(address, event_class, event)])

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            format_discovered_event_class(address),
            _async_discovered_event_class,
        )
    )
