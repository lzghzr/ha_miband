"""Config flow for MiBand integration."""

import asyncio
import dataclasses
import logging
from dataclasses import asdict
from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfo,
    async_discovered_service_info,
    async_process_advertisements,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .cloud import (
    XiaomiCloudException,
    XiaomiCloudInvalidAuthenticationException,
    XiaomiCloudTokenFetch,
)
from .const import DOMAIN
from .parser import XiaomiBluetoothDeviceData as DeviceData

# How long to wait for additional advertisement packets if we don't have the right ones
ADDITIONAL_DISCOVERY_TIMEOUT = 60

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class Discovery:
    """A discovered bluetooth device."""

    title: str
    discovery_info: BluetoothServiceInfo
    device: DeviceData


def _title(discovery_info: BluetoothServiceInfo, device: DeviceData) -> str:
    return device.title or device.get_device_name() or discovery_info.name


class MiBandConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MiBand."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_device: DeviceData | None = None
        self._discovered_devices: dict[str, Discovery] = {}
        self._discovery_info: BluetoothServiceInfo | None = None
        self._fetcher: XiaomiCloudTokenFetch | None = None
        self._login_task: asyncio.Task | None = None

    async def _async_wait_for_full_advertisement(
        self, discovery_info: BluetoothServiceInfo, device: DeviceData
    ) -> BluetoothServiceInfo:
        """Sometimes first advertisement we receive is blank or incomplete.

        Wait until we get a useful one.
        """
        if not device.pending:
            return discovery_info

        def _process_more_advertisements(
            service_info: BluetoothServiceInfo,
        ) -> bool:
            device.update(service_info)
            return not device.pending

        return await async_process_advertisements(
            self.hass,
            _process_more_advertisements,
            {"address": discovery_info.address},
            BluetoothScanningMode.ACTIVE,
            ADDITIONAL_DISCOVERY_TIMEOUT,
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        device = DeviceData()
        if not device.supported(discovery_info):
            return self.async_abort(reason="not_supported")

        title = _title(discovery_info, device)
        self.context["title_placeholders"] = {"name": title}

        self._discovered_device = device

        # Wait until we have received enough information about
        # this device to detect its encryption type
        try:
            self._discovery_info = await self._async_wait_for_full_advertisement(
                discovery_info, device
            )
        except TimeoutError:
            # This device might have a really long advertising interval
            # So create a config entry for it, and if we discover it has
            # encryption later, we can do a reauth
            return await self.async_step_confirm_slow()

        return await self.async_step_get_encryption_key_4_5_choose_method()

    async def async_step_get_encryption_key_4_5(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enter a bindkey for a v4/v5 MiBeacon device."""
        assert self._discovery_info
        assert self._discovered_device

        errors = {}

        if user_input is not None:
            bindkey = user_input["bindkey"]

            if len(bindkey) != 32:
                errors["bindkey"] = "expected_32_characters"
            else:
                self._discovered_device.set_bindkey(bytes.fromhex(bindkey))

                # If we got this far we already know supported will
                # return true so we don't bother checking that again
                # We just want to retry the decryption
                self._discovered_device.supported(self._discovery_info)

                if self._discovered_device.bindkey_verified:
                    pd_id = self._discovered_device.device_id
                    return self._async_get_or_create_entry(bindkey, pd_id)

                errors["bindkey"] = "decryption_failed"

        return self.async_show_form(
            step_id="get_encryption_key_4_5",
            description_placeholders=self.context["title_placeholders"],
            data_schema=vol.Schema({vol.Required("bindkey"): vol.All(str, vol.Strip)}),
            errors=errors,
        )

    async def async_step_password_cloud_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the cloud auth step."""
        assert self._discovery_info

        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            self._fetcher = XiaomiCloudTokenFetch(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD], session
            )
            try:
                device_details = await self._fetcher.get_device_info(
                    self._discovery_info.address
                )
            except XiaomiCloudInvalidAuthenticationException as ex:
                _LOGGER.debug("Authentication failed: %s", ex, exc_info=True)
                errors = {"base": "auth_failed"}
                description_placeholders = {"error_detail": str(ex)}
            except XiaomiCloudException as ex:
                _LOGGER.debug("Failed to connect to MI API: %s", ex, exc_info=True)
                raise AbortFlow(
                    "api_error", description_placeholders={"error_detail": str(ex)}
                ) from ex
            else:
                if device_details:
                    return await self.async_step_get_encryption_key_4_5(
                        {"bindkey": device_details.bindkey}
                    )
                errors = {"base": "api_device_not_found"}

        user_input = user_input or {}
        return self.async_show_form(
            step_id="password_cloud_auth",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME)
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={
                **self.context["title_placeholders"],
                **description_placeholders,
            },
        )

    async def async_step_qrcode_cloud_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._fetcher is None:
            session = async_get_clientsession(self.hass)
            self._fetcher = XiaomiCloudTokenFetch(session=session)

        try:
            login_qrcode = await self._fetcher.get_login_qrcode()
        except XiaomiCloudInvalidAuthenticationException as ex:
            _LOGGER.debug("Failed to connect to MI API: %s", ex, exc_info=True)
            raise AbortFlow(
                "api_error", description_placeholders={"error_detail": str(ex)}
            ) from ex

        async def _wait_for_authorization() -> None:
            _LOGGER.debug("Waiting for device authorization")
            try:
                self._device_details = await self._fetcher.get_device_info(
                    self._discovery_info.address
                )
                _LOGGER.debug("Authorization successful")
            except XiaomiCloudInvalidAuthenticationException as ex:
                _LOGGER.debug("Failed to connect to MI API: %s", ex, exc_info=True)
                raise AbortFlow(
                    "api_error", description_placeholders={"error_detail": str(ex)}
                ) from ex

        if self._login_task is None:
            _LOGGER.debug("Creating task for device authorization")
            self._login_task = self.hass.async_create_task(_wait_for_authorization())

        if self._login_task.done():
            _LOGGER.debug("Login task is done, checking results")
            if exception := self._login_task.exception():
                if isinstance(exception, AbortFlow):
                    return self.async_show_progress_done(
                        next_step_id="qrcode_connection_error"
                    )
                return self.async_show_progress_done(
                    next_step_id="qrcode_connection_error"
                )
            return self.async_show_progress_done(next_step_id="qrcode_finish_login")

        return self.async_show_progress(
            step_id="qrcode_cloud_auth",
            progress_action="wait_for_authorization",
            description_placeholders=asdict(login_qrcode),
            progress_task=self._login_task,
        )

    async def async_step_qrcode_finish_login(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the finalization of login."""
        _LOGGER.debug("Finalizing authorization")
        if self._device_details:
            return await self.async_step_get_encryption_key_4_5(
                {"bindkey": self._device_details.bindkey}
            )
        return self.async_abort(reason="no_devices_found")

    async def async_step_qrcode_connection_error(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle connection error from progress step."""
        if user_input is None:
            return self.async_show_form(
                step_id="qrcode_connection_error",
                description_placeholders=self.context["title_placeholders"],
            )
        # Reset state and try again
        self._device_details = None
        self._fetcher = None
        self._login_task = None
        return await self.async_step_get_encryption_key_4_5_choose_method()

    async def async_step_get_encryption_key_4_5_choose_method(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose method to get the bind key for a version 4/5 device."""
        return self.async_show_menu(
            step_id="get_encryption_key_4_5_choose_method",
            menu_options=[
                "qrcode_cloud_auth",
                "password_cloud_auth",
                "get_encryption_key_4_5",
            ],
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_confirm_slow(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ack that device is slow."""
        if user_input is not None:
            return self._async_get_or_create_entry()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="confirm_slow",
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            discovery = self._discovered_devices[address]

            self.context["title_placeholders"] = {"name": discovery.title}

            # Wait until we have received enough information about
            # this device to detect its encryption type
            try:
                self._discovery_info = await self._async_wait_for_full_advertisement(
                    discovery.discovery_info, discovery.device
                )
            except TimeoutError:
                # This device might have a really long advertising interval
                # So create a config entry for it, and if we discover
                # it has encryption later, we can do a reauth
                return await self.async_step_confirm_slow()

            self._discovered_device = discovery.device

            return await self.async_step_get_encryption_key_4_5_choose_method()

        current_addresses = self._async_current_ids(include_ignore=False)
        for discovery_info in async_discovered_service_info(self.hass, False):
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                continue
            device = DeviceData()
            if device.supported(discovery_info):
                self._discovered_devices[address] = Discovery(
                    title=_title(discovery_info, device),
                    discovery_info=discovery_info,
                    device=device,
                )

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        titles = {
            address: discovery.title
            for (address, discovery) in self._discovered_devices.items()
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(titles)}),
        )

    def _async_get_or_create_entry(
        self, bindkey: str | None = None, pd_id: int | None = None
    ) -> ConfigFlowResult:
        data: dict[str, Any] = {}

        if bindkey:
            data["bindkey"] = bindkey

        if pd_id:
            data["pd_id"] = pd_id

        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )

        return self.async_create_entry(
            title=self.context["title_placeholders"]["name"],
            data=data,
        )
