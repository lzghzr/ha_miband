"""The MiBand integration."""

from functools import partial
import logging
from typing import cast

from homeassistant.components.bluetooth import (
    DOMAIN as BLUETOOTH_DOMAIN,
    BluetoothServiceInfoBleak,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceRegistry
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    DOMAIN,
    MIBAND_EVENT,
    MiBandEvent,
)
from .coordinator import (
    MiBandCoordinator,
    MiBandConfigEntry,
)
from .device import DEVICE_TYPES
from .parser import XiaomiBluetoothDeviceData, SensorUpdate


PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.EVENT, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


def process_service_info(
    hass: HomeAssistant,
    entry: MiBandConfigEntry,
    device_registry: DeviceRegistry,
    service_info: BluetoothServiceInfoBleak,
) -> SensorUpdate:
    coordinator = entry.runtime_data
    data = coordinator.device_data
    update = data.update(service_info)
    if update.events:
        address = service_info.device.address
        for device_key, event in update.events.items():
            device = device_registry.async_get_device(
                connections={(CONNECTION_BLUETOOTH, address)},
                identifiers={(BLUETOOTH_DOMAIN, address)},
            )
            event_class = event.device_key.key
            event_type = event.event_type

            miband_event = MiBandEvent(
                device_id=device.id,
                address=address,
                event_class=event_class,
                event_type=event_type,
                translation_key=event_class,
                event_properties=event.event_properties,
            )

            hass.bus.async_fire(MIBAND_EVENT, cast(dict, miband_event))
            async_dispatcher_send(
                hass,
                format_event_dispatcher_name(address, event_class),
                miband_event,
            )

    # If device isn't pending we know it has seen at least one broadcast with a payload
    # If that payload was encrypted and the bindkey was not verified then we need to reauth
    if not data.pending and not data.bindkey_verified:
        entry.async_start_reauth(hass, data={"device": data})

    return update


def format_event_dispatcher_name(address: str, event_class: str) -> str:
    """Format an event dispatcher name."""
    return f"{DOMAIN}_event_{address}_{event_class}"


def format_discovered_event_class(address: str) -> str:
    """Format a discovered event class."""
    return f"{DOMAIN}_discovered_event_class_{address}"


async def async_setup_entry(hass: HomeAssistant, entry: MiBandConfigEntry) -> bool:
    """Set up MiBand from a config entry."""
    address = entry.unique_id
    bindkey = entry.data.get("bindkey")
    pd_id = entry.data.get("pd_id")
    assert address is not None and bindkey is not None and pd_id is not None

    kwargs = {"bindkey": bytes.fromhex(bindkey)}
    data = XiaomiBluetoothDeviceData(**kwargs)

    device_registry = dr.async_get(hass)

    device = DEVICE_TYPES[pd_id]
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(CONNECTION_BLUETOOTH, address)},
        identifiers={(BLUETOOTH_DOMAIN, address)},
        manufacturer=device.manufacturer,
        model=device.model,
        name=device.name,
    )

    coordinator = MiBandCoordinator(
        hass,
        _LOGGER,
        address,
        update_method=partial(process_service_info, hass, entry, device_registry),
        device_data=data,
        entry=entry,
    )
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # only start after all platforms have had a chance to subscribe
    entry.async_on_unload(coordinator.async_start())
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MiBandConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
