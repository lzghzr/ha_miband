"""An incomplete MiBeacon can be retried without starting configuration over."""
import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from test_entity_upgrade import KEY, MAC, PID, ROOT, advertisement


@pytest.mark.parametrize("source", ["bluetooth", "user"])
def test_retry_same_device_until_complete(source, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    from custom_components.miband import config_flow

    async def run():
        first = advertisement(PID, 0x6461, b"\x01", 1)
        first.service_data[next(iter(first.service_data))] = b"\x00\x50" + PID.to_bytes(2, "little") + b"\x01"
        complete = advertisement(PID, 0x6461, b"\x01", 2)
        flow = config_flow.MiBandConfigFlow()
        flow.hass = Mock()
        flow.context = {"source": source}

        async def receive(_hass, callback, matcher, _mode, timeout):
            assert matcher == {"address": MAC} and timeout == 60
            assert not callback(first)
            assert callback(complete)
            return complete

        with (patch.object(flow, "async_set_unique_id", new=AsyncMock()),
              patch.object(flow, "_abort_if_unique_id_configured"),
              patch.object(flow, "_async_current_ids", return_value=set()),
              patch.object(config_flow, "async_discovered_service_info", return_value=[first]),
              patch.object(config_flow, "async_process_advertisements", new_callable=AsyncMock) as scan):
            scan.side_effect = TimeoutError
            if source == "bluetooth":
                result = await flow.async_step_bluetooth(first)
            else:
                assert (await flow.async_step_user())["step_id"] == "user"
                result = await flow.async_step_user({"address": MAC})
            assert (result["type"], result["step_id"]) == ("form", "retry_discovery")
            assert (await flow.async_step_retry_discovery({}))["step_id"] == "retry_discovery"
            scan.side_effect = receive
            result = await flow.async_step_retry_discovery({})
            assert result["type"] == "menu"
            assert "qrcode_cloud_auth" in result["menu_options"]
            result = await flow.async_step_get_encryption_key_4_5({"bindkey": KEY.hex()})
            assert (result["type"], result["data"]) == ("create_entry", {"bindkey": KEY.hex(), "pd_id": PID})

    asyncio.run(run())


def test_complete_first_broadcast_skips_wait(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    from custom_components.miband import config_flow

    async def run():
        flow = config_flow.MiBandConfigFlow()
        flow.hass = Mock()
        flow.context = {"source": "bluetooth"}
        with (patch.object(flow, "async_set_unique_id", new=AsyncMock()),
              patch.object(flow, "_abort_if_unique_id_configured"),
              patch.object(config_flow, "async_process_advertisements", new_callable=AsyncMock) as scan):
            result = await flow.async_step_bluetooth(advertisement(PID, 0x6461, b"\x01", 1))
            assert result["step_id"] == "get_encryption_key_4_5_choose_method"
            scan.assert_not_awaited()

    asyncio.run(run())
