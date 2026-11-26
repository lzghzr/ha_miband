"""Install the actual 0.3.6 tag, restart HA on the new component, reuse its storage."""
import asyncio
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from types import MappingProxyType, SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def test_upgrade_from_0_3_6(tmp_path):
    installed = tmp_path / "custom_components/miband"
    installed.mkdir(parents=True)
    archive = subprocess.check_output(["git", "archive", "0.3.6"], cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(installed, filter="data")

    def boot(phase):
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), str(tmp_path), phase],
            cwd=tmp_path, check=True, timeout=90,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(tmp_path)},
        )

    boot("before")
    shutil.rmtree(installed)
    shutil.copytree(ROOT / "custom_components/miband", installed)
    boot("after")


async def run_install(config_dir, before):
    from homeassistant import bootstrap, config_entries, loader
    from homeassistant.components.bluetooth import BluetoothChange, passive_update_processor
    from homeassistant.components.bluetooth.const import DATA_MANAGER
    from homeassistant.components.homeassistant.triggers import state
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from test_entity_upgrade import KEY, MAC, PID, advertisement

    hass = HomeAssistant(str(config_dir))
    hass.config.skip_pip = True
    loader.async_setup(hass)
    hass.config_entries = config_entries.ConfigEntries(hass, {})
    assert await bootstrap.async_load_base_functionality(hass)
    component = await loader.async_get_integration(hass, "miband")
    module = await component.async_get_component()
    assert Path(module.__file__).parent == config_dir / "custom_components/miband"
    assert component.version == ("0.3.6" if before else json.loads(
        (ROOT / "custom_components/miband/manifest.json").read_bytes())["version"])

    # Supply the radio boundary only; HA manages the entries, platforms and registries.
    hass.config.components.add("bluetooth_adapters")
    hass.data[DATA_MANAGER] = SimpleNamespace(
        async_address_present=lambda *_: False, async_last_service_info=lambda *_: None,
    )
    await passive_update_processor.async_setup(hass)
    with patch.object(module.MiBandCoordinator, "async_start", return_value=lambda: None):
        if before:
            entry = config_entries.ConfigEntry(
                version=1, minor_version=1, domain="miband", unique_id=MAC,
                title="测试手环", data={"pd_id": PID, "bindkey": KEY.hex()}, options={},
                source="user", discovery_keys=MappingProxyType({}), subentries_data=None,
            )
            await hass.config_entries.async_add(entry)
        else:
            entry, = hass.config_entries.async_entries("miband")
            assert await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert entry.unique_id == MAC and entry.data == {"pd_id": PID, "bindkey": KEY.hex()}
    await hass.async_block_till_done()

    devices, entities = dr.async_get(hass), er.async_get(hass)
    device, = dr.async_entries_for_config_entry(devices, entry.entry_id)
    oracle = config_dir / "before.json"

    def snapshot():
        return {e.unique_id: [e.id, e.entity_id, e.device_id, e.name]
                for e in er.async_entries_for_config_entry(entities, entry.entry_id)}

    async def receive(oid, value, count):
        entry.runtime_data._async_handle_bluetooth_event(
            advertisement(PID, oid, value, count), BluetoothChange.ADVERTISEMENT)
        await hass.async_block_till_done()

    if before:
        await receive(0x6461, b"\x01", 1)
        await receive(0x4E5B, bytes([8, 0, 0, 0, 0]), 2)
        await receive(0x5422, b"\x01", 3)
        wearing = snapshot()[f"{MAC}-wearing"][1]
        renamed = entities.async_update_entity(
            wearing, new_entity_id="binary_sensor.my_band_wearing", name="我的佩戴状态")
        devices.async_update_device(device.id, name_by_user="我的手环")
        await hass.async_block_till_done()
        rows = snapshot()
        assert f"{MAC}-no_disturb" not in rows
        assert {v[1].partition(".")[0] for v in rows.values()} == {"sensor", "binary_sensor", "event"}
        assert hass.states.get(renamed.entity_id).state == "on"
        assert hass.states.get(rows[f"{MAC}_sports"][1]).attributes["event_type"] == "sport_start"
        assert hass.states.get(rows[f"{MAC}-battery_charging"][1]).state == "charging_disconnected"
        oracle.write_text(json.dumps({
            "entry": entry.entry_id, "device": device.id, "rows": rows,
            "trigger": {"platform": "state", "entity_id": renamed.entity_id, "from": "on", "to": "off"},
        }))
    else:
        old = json.loads(oracle.read_bytes())
        rows = snapshot()
        assert (entry.entry_id, device.id, device.name_by_user) == (old["entry"], old["device"], "我的手环")
        assert {uid: rows[uid] for uid in old["rows"]} == old["rows"]
        assert all(identifiers[2] == device.id for identifiers in rows.values())
        mode = rows[f"{MAC}-no_disturb"][1]
        assert hass.states.get(mode).state == "unknown"
        fired = []

        async def record(variables, context):
            fired.append(variables["trigger"]["entity_id"])

        trigger = await state.async_validate_trigger_config(hass, old["trigger"])
        unsub = await state.async_attach_trigger(
            hass, trigger, record, {"variables": {}, "trigger_data": {}})
        await receive(0x6461, b"\x01", 4)
        await receive(0x6461, b"\x00", 5)
        assert fired == [old["trigger"]["entity_id"]]
        unsub()
        await receive(0x4E5B, bytes([8, 0, 0, 0, 1]), 6)
        assert hass.states.get(old["rows"][f"{MAC}_sports"][1]).attributes["event_type"] == "sport_end"
        await receive(0x6669, b"\x02", 7)
        assert hass.states.get(mode).state == "on"
        await receive(0x5422, b"\x02", 8)
        assert hass.states.get(old["rows"][f"{MAC}-battery_charging"][1]).state == "charging_complete"
    await hass.async_stop(force=True)


if __name__ == "__main__":
    asyncio.run(run_install(Path(sys.argv[1]), before=sys.argv[2] == "before"))
