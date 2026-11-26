"""Existing config entries, before and after the first broadcast (HA 2026.11.3)."""
import asyncio
import importlib
import logging
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESCCM
from homeassistant import bootstrap, config_entries, loader
from homeassistant.components.bluetooth import BluetoothChange, passive_update_processor
from homeassistant.components.bluetooth.const import DATA_MANAGER
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import EntityPlatform

ROOT = Path(__file__).resolve().parents[2]
PID = 0x59FC
MAC = "02:00:00:00:00:01"
KEY = bytes(range(16))  # Synthetic fixture, not a device key.


def advertisement(pid, oid, payload, count):
    counter = bytes([count])
    product = pid.to_bytes(2, "little")
    extra = b"\x10\x20\x30"
    nonce = bytes.fromhex(MAC.replace(":", ""))[::-1] + product + counter + extra
    plain = oid.to_bytes(2, "little") + bytes([len(payload)]) + payload
    encrypted = AESCCM(KEY, tag_length=4).encrypt(nonce, plain, b"\x11")
    frame = b"\x48\x50" + product + counter + encrypted[:-4] + extra + encrypted[-4:]
    return SimpleNamespace(
        address=MAC, name="Band", rssi=-50, device=SimpleNamespace(address=MAC),
        service_data={"0000fe95-0000-1000-8000-00805f9b34fb": frame}, time=count,
    )


def mode_frame(pid, oid, value, count):
    return advertisement(pid, oid, bytes([value]), count)


@pytest.fixture
def integration(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    miband = importlib.import_module("custom_components.miband")
    modules = {
        domain: importlib.import_module(f"custom_components.miband.{domain}")
        for domain in ("sensor", "binary_sensor", "event")
    }
    return miband, modules


@asynccontextmanager
async def configured_band(config_dir, integration):
    miband, modules = integration
    hass = HomeAssistant(str(config_dir))
    hass.config.language = "zh-Hans"
    loader.async_setup(hass)
    hass.config_entries = config_entries.ConfigEntries(hass, {})
    assert await bootstrap.async_load_base_functionality(hass)
    await passive_update_processor.async_setup(hass)
    hass.data[DATA_MANAGER] = SimpleNamespace(async_address_present=lambda *_: False, async_last_service_info=lambda *_: None)
    entry = config_entries.ConfigEntry(
        data={"pd_id": PID, "bindkey": KEY.hex()}, unique_id=MAC, title="手环 10",
        domain="miband", minor_version=1, version=1, source="user", options={},
        discovery_keys=MappingProxyType({}), subentries_data=None,
    )
    with patch.object(hass.config_entries, "async_setup", new=AsyncMock(return_value=True)):
        await hass.config_entries.async_add(entry)

    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "binary_sensor", "miband", f"{MAC}-wearing", config_entry=entry,
        suggested_object_id="previous_wearing",
    )
    registry.async_update_entity(old.entity_id, name="自定义佩戴名称")
    wearing = PassiveBluetoothEntityKey("wearing", None)
    restored = PassiveBluetoothDataUpdate(
        entity_descriptions={wearing: modules["binary_sensor"].BINARY_SENSOR_DESCRIPTIONS["wearing"]},
        entity_data={wearing: False},
    )
    events = []
    hass.bus.async_listen("miband_event", lambda ev: events.append(ev.data))

    active_platforms = []

    async def forward(entry, platforms):
        entry.runtime_data.restore_data["binary_sensor"] = restored.async_get_restore_data()
        for domain in platforms:
            platform = EntityPlatform(
                hass=hass, logger=logging.getLogger("test"), domain=domain, platform_name="miband",
                platform=modules[domain], scan_interval=timedelta(seconds=60), entity_namespace=None,
            )
            assert await platform.async_setup_entry(entry)
            active_platforms.append(platform)

    async def setup():
        token = config_entries.current_entry.set(entry)
        try:
            with (patch.object(hass.config_entries, "async_forward_entry_setups", new=forward),
                  patch.object(miband.MiBandCoordinator, "async_start", return_value=lambda: None)):
                assert await miband.async_setup_entry(hass, entry)
        finally:
            config_entries.current_entry.reset(token)
        await hass.async_block_till_done()

    async def reload():
        for platform in active_platforms:
            await platform.async_reset()
        active_platforms.clear()
        await entry._async_process_on_unload(hass)
        await setup()

    await setup()

    def ids():
        return {r.unique_id: r.entity_id for r in er.async_entries_for_config_entry(registry, entry.entry_id)}

    def state(entity_id):
        return hass.states.get(entity_id).state

    try:
        yield SimpleNamespace(
            hass=hass, entry=entry, registry=registry, old=old, events=events,
            ids=ids, state=state, reload=reload,
        )
    finally:
        await hass.async_stop()


def test_existing_entry_gains_entities_before_any_broadcast(tmp_path, integration):
    asyncio.run(check_upgrade(tmp_path, integration))


def test_cloud_key_is_returned_privately(integration, caplog):
    cloud = importlib.import_module("custom_components.miband.cloud")
    fetch = cloud.XiaomiCloudTokenFetch()
    device = {"name": "fixture-personal-name", "detail": {"mac": MAC, "beaconkey": KEY.hex()}}
    fetch._connector = SimpleNamespace(
        login=AsyncMock(), userId="fixture-account",
        get_devices=AsyncMock(return_value={"result": {"list": [device]}}),
    )
    with caplog.at_level(logging.DEBUG, logger=cloud.__name__):
        result = asyncio.run(fetch.get_device_info(MAC, ["cn"]))
    assert (result.name, result.mac, result.bindkey) == (device["name"], MAC, KEY.hex())
    for private in (device["name"], MAC, KEY.hex(), "fixture-account"):
        assert private not in caplog.text


def test_frame_diagnostics_keep_ids_not_device_data(integration, caplog):
    miband, _ = integration
    sample = b"fixture-private-payload"
    frame = advertisement(PID, 0xFADE, sample, 1)
    logger = miband.XiaomiBluetoothDeviceData.__module__
    with caplog.at_level(logging.DEBUG, logger=logger):
        miband.XiaomiBluetoothDeviceData(KEY).update(frame)
        miband.XiaomiBluetoothDeviceData(KEY[::-1]).update(frame)
        miband.XiaomiBluetoothDeviceData(KEY).update(advertisement(0xFFFE, 0xFADE, sample, 2))
    messages = "\n".join(r.getMessage() for r in caplog.records if r.name == logger)
    for reason in ("0xFADE", f"0x{PID:04X}", "0xFFFE", "authentication failed"):
        assert reason in messages
    packet = next(iter(frame.service_data.values()))
    for private in (MAC, MAC.replace(":", ""), bytes.fromhex(MAC.replace(":", ""))[::-1].hex(),
                    sample.hex(), sample.decode(), packet.hex(), packet[5:-7].hex(), packet[-4:].hex()):
        assert private not in messages


def test_high_pressure_event_value(integration):
    miband, _ = integration
    update = miband.XiaomiBluetoothDeviceData(KEY).update(mode_frame(PID, 0x4E5C, 4, 1))
    assert [event.event_type for event in update.events.values()] == ["high_pressure"]


async def check_upgrade(config_dir, integration):
    miband, _ = integration
    async with configured_band(config_dir, integration) as band:
        hass, coord, registry = band.hass, band.entry.runtime_data, band.registry
        old, events, ids, state = band.old, band.events, band.ids, band.state
        before = ids()
        dnd, mode = before[f"{MAC}-no_disturb"], before[f"{MAC}_mode"]
        assert before[f"{MAC}-wearing"] == old.entity_id
        assert state(old.entity_id) == "off" and registry.async_get(old.entity_id).name == "自定义佩戴名称"
        assert all(state(eid) == "unknown" for eid in (dnd, mode, before[f"{MAC}-battery_charging"]))
        assert f"{MAC}-mute" not in before
        assert not events and coord.device_data.pending and not coord.available

        for count, (raw, on_off) in enumerate(((2, "on"), (3, "off")), 1):
            coord._async_handle_bluetooth_event(mode_frame(PID, 0x6669, raw, count), BluetoothChange.ADVERTISEMENT)
            await hass.async_block_till_done()
            assert state(dnd) == on_off
            assert events[-1]["event_type"] == f"no_disturb_{on_off}"
            assert hass.states.get(mode).attributes["event_type"] == events[-1]["event_type"]
        assert len(events) == 2
        assert all(ids()[key] == eid for key, eid in before.items())
        assert len(ids()) == len(before) + 1  # Only real RSSI is added on receive.

        # All three object IDs carry the same one-byte mode event.
        for pid, oid, raw, event_type, sensor_values in (
            (PID, 0x6669, 0, "mute_on", {"mute": True}),
            (PID, 0x6E69, 2, "no_disturb_on", {"no_disturb": True}),
            (0x4F2A, 0x6E69, 0, "mute_on", {"mute": True}),
            (0x4F2B, 0x6E69, 1, "mute_off", {"mute": False}),
            (0x4F2A, 0x6E69, 3, "no_disturb_off", {"no_disturb": False}),
            (0x6B4D, 0x5E69, 0, "mute_on", {"mute": True}),
            (PID, 0x6669, 0xFF, "other", {}),
        ):
            update = miband.XiaomiBluetoothDeviceData(KEY).update(mode_frame(pid, oid, raw, 5))
            assert [event.event_type for event in update.events.values()] == [event_type]
            assert {k.key: v.native_value for k, v in update.binary_entity_values.items()} == sensor_values


def test_discovered_event_becomes_prebuilt(tmp_path, integration):
    asyncio.run(check_discovery(tmp_path, integration))


async def check_discovery(config_dir, integration):
    miband, _ = integration
    model = miband.DEVICE_TYPES[PID]
    old_model = replace(model, event=[key for key in model.event if key != "sports"])
    unique_id = f"{MAC}_sports"

    with patch.dict(miband.DEVICE_TYPES, {PID: old_model}):
        async with configured_band(config_dir, integration) as band:
            assert unique_id not in band.ids()

            async def broadcast(counter, value):
                frame = advertisement(PID, 0x4E5B, bytes([8, 0, 0, 0, value]), counter)
                band.entry.runtime_data._async_handle_bluetooth_event(frame, BluetoothChange.ADVERTISEMENT)
                await band.hass.async_block_till_done()

            await broadcast(1, 0)
            entity_id = band.ids()[unique_id]
            first = band.hass.states.get(entity_id)
            assert first.state != "unknown"
            assert first.attributes["event_type"] == "sport_start"
            assert first.attributes["sport_type"] == "free_training"
            assert len(band.events) == 1
            original = band.registry.async_update_entity(entity_id, name="我的运动")
            original_ids = band.ids()

            await broadcast(2, 2)
            assert band.ids() == original_ids
            assert band.hass.states.get(entity_id).attributes["event_type"] == "sport_pause"
            assert len(band.events) == 2

            # Reload before and after the model table includes the discovered event.
            for counter, table in enumerate((old_model, model), start=3):
                with patch.dict(miband.DEVICE_TYPES, {PID: table}):
                    previous = band.hass.states.get(entity_id)
                    await band.reload()
                    restored = band.hass.states.get(entity_id)
                    assert restored.state == previous.state
                    assert restored.attributes == previous.attributes
                    assert len(band.events) == counter - 1
                    await broadcast(counter, 1)
                    current = band.hass.states.get(entity_id)
                    assert current.attributes["event_type"] == "sport_end"
                    assert current.attributes["sport_type"] == "free_training"
                    assert current.state != restored.state
                    assert len(band.events) == counter
                    assert band.ids() == original_ids
                    assert band.registry.async_get(entity_id).id == original.id
                    assert band.registry.async_get(entity_id).name == "我的运动"
