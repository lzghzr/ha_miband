"""Support for MiBand event entities."""

from homeassistant.components.event import (
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import format_discovered_event_class, format_event_dispatcher_name
from .const import (
    ABNORMAL_VITAL_SIGNS_TYPE,
    DOMAIN,
    EVENT_PROPERTIES,
    EVENT_TYPE,
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
    MiBandEventDeviceClass.SPORTS: EventEntityDescription(
        key=MiBandEventDeviceClass.SPORTS,
        event_types=list(SPORT_EVENT_TYPE.values()),
        translation_key=MiBandEventDeviceClass.SPORTS,
    ),
}


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
        self._attr_unique_id = f"{address}_{event_class}"
        # If the event is provided then we can set the initial state
        # since the event itself is likely what triggered the creation
        # of this entity. We have to do this at creation time since
        # entities are created dynamically and would otherwise miss
        # the initial state.
        if event:
            self._trigger_event(event[EVENT_TYPE], event[EVENT_PROPERTIES])

    async def async_added_to_hass(self) -> None:
        """Entity added to hass."""
        await super().async_added_to_hass()
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
    async_add_entities(MiBandEventEntity(address, key, None) for key in device.event)

    @callback
    def _async_discovered_event_class(event_class: str, event: MiBandEvent) -> None:
        """Handle a newly discovered event class with or without a postfix."""
        async_add_entities([MiBandEventEntity(address, event_class, event)])

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            format_discovered_event_class(address),
            _async_discovered_event_class,
        )
    )
