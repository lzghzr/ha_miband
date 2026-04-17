"""Parser for Xiaomi BLE advertisements.
This file is shamlessly copied from the following repository:
https://github.com/Ernst79/bleparser/blob/c42ae922e1abed2720c7fac993777e1bd59c0c93/package/bleparser/xiaomi.py
MIT License applies.
"""

import logging
from typing import Any

from sensor_state_data import (
    DeviceKey,
    Event,
    SensorDeviceInfo,
    SensorUpdate,
    SensorDescription,
    BinarySensorDescription,
)

from bluetooth_data_tools import short_address
from bluetooth_sensor_state_data import BluetoothData
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESCCM
from home_assistant_bluetooth import BluetoothServiceInfo


from .const import (
    ABNORMAL_VITAL_SIGNS_TYPE,
    BATTERY_CHARGING_STATE,
    HAND_GESTURE_TYPE,
    SERVICE_MIBEACON,
    SPORT_EVENT_TYPE,
    SPORT_TYPE,
    VITALITY_GOAL_TYPE,
    MiBandBinarySensorDeviceClass,
    MiBandEventDeviceClass,
    MiBandSensorDeviceClass,
)
from .device import DEVICE_TYPES

_LOGGER = logging.getLogger(__name__)


def to_mac(addr: bytes) -> str:
    """Return formatted MAC address"""
    return ":".join(f"{i:02X}" for i in addr)


def to_unformatted_mac(addr: str) -> str:
    """Return unformatted MAC address"""
    return "".join(f"{i:02X}" for i in addr[:])


def parse_event_properties(
    event_property: str | None, value: int
) -> dict[str, int | None] | None:
    """Convert event property and data to event properties."""
    if event_property:
        return {event_property: value}
    return None


def eiid1016(
    xobj: bytes, device: XiaomiBluetoothDeviceData, device_type: str
) -> dict[str, Any]:
    """Sleep"""
    if len(xobj) != 1:
        return {}
    device.update_binary_sensor(
        key=MiBandBinarySensorDeviceClass.SLEEP,
        native_value=xobj[0],
        device_class=MiBandBinarySensorDeviceClass.SLEEP,
    )
    return {}


def eiid1034(
    xobj: bytes, device: XiaomiBluetoothDeviceData, device_type: str
) -> dict[str, Any]:
    """Battery Charging"""
    if len(xobj) != 1:
        return {}
    device.update_sensor(
        key=MiBandSensorDeviceClass.BATTERY_CHARGING,
        native_value=BATTERY_CHARGING_STATE.get(xobj[0], "other"),
        native_unit_of_measurement=None,
        device_class=MiBandSensorDeviceClass.BATTERY_CHARGING,
    )
    return {}


def eiid1086(
    xobj: bytes, device: XiaomiBluetoothDeviceData, device_type: str
) -> dict[str, Any]:
    """Hand Gesture"""
    if len(xobj) != 1:
        return {}
    device.fire_event(
        key=MiBandEventDeviceClass.HAND_GESTURE,
        event_type=HAND_GESTURE_TYPE.get(xobj[0], "other"),
        event_properties=None,
    )
    return {}


def eiid1091(
    xobj: bytes, device: XiaomiBluetoothDeviceData, device_type: str
) -> dict[str, Any]:
    """Sports"""
    if len(xobj) != 5:
        return {}
    sport_id = int.from_bytes(xobj[0:3], "little")
    sport_type = SPORT_TYPE.get(sport_id, f"other_{sport_id}")
    device.fire_event(
        key=MiBandEventDeviceClass.SPORTS,
        event_type=SPORT_EVENT_TYPE.get(xobj[-1], "other"),
        event_properties={"sport_type": sport_type},
    )
    return {}


def eiid1092(
    xobj: bytes, device: XiaomiBluetoothDeviceData, device_type: str
) -> dict[str, Any]:
    """Abnormal Signs"""
    if len(xobj) != 1:
        return {}
    device.fire_event(
        key=MiBandEventDeviceClass.ABNORMAL_SIGNS,
        event_type=ABNORMAL_VITAL_SIGNS_TYPE.get(xobj[0], "other"),
        event_properties=None,
    )
    return {}


def eiid1094(
    xobj: bytes, device: XiaomiBluetoothDeviceData, device_type: str
) -> dict[str, Any]:
    """Daily Vitality Index"""
    if len(xobj) != 1:
        return {}
    device.fire_event(
        key=MiBandEventDeviceClass.DAILY_VITALITY_INDEX,
        event_type=VITALITY_GOAL_TYPE.get(xobj[0], "other"),
        event_properties=None,
    )
    return {}


def eiid1097(
    xobj: bytes, device: XiaomiBluetoothDeviceData, device_type: str
) -> dict[str, Any]:
    """Wearing"""
    if len(xobj) != 1:
        return {}
    device.update_binary_sensor(
        key=MiBandBinarySensorDeviceClass.WEARING,
        native_value=xobj[0],
        device_class=MiBandBinarySensorDeviceClass.WEARING,
    )
    return {}


# Dataobject dictionary
# {dataObject_id: (converter}
# maybe
# property_id = eiid + 0x400 * siid + 0x3C18
# event_id = eiid + 0x400 * siid + 0x3E18
xiaomi_dataobject_dict = {
    0x4810: eiid1016,
    0x5810: eiid1016,
    0x5422: eiid1034,
    0x5822: eiid1034,
    0x5656: eiid1086,
    0x4E5B: eiid1091,
    0x525B: eiid1091,
    0x4E5C: eiid1092,
    0x525C: eiid1092,
    0x4E5E: eiid1094,
    0x525E: eiid1094,
    0x5C61: eiid1097,
    0x6461: eiid1097,
    0x6C61: eiid1097,
}


class XiaomiBluetoothDeviceData(BluetoothData):
    """Data for Xiaomi BLE sensors."""

    def __init__(self, bindkey: bytes | None = None) -> None:
        super().__init__()
        self.set_bindkey(bindkey)

        # Data that we know how to parse but don't yet map to the SensorData model.
        self.unhandled: dict[str, Any] = {}

        # If true then we have used the provided encryption key to decrypt at least
        # one payload.
        # If false then we have either not seen an encrypted payload, the key is wrong
        # or encryption is not in use
        self.bindkey_verified = False

        # If True then the decryption has failed or has not been verified yet.
        # If False then the decryption has succeeded.
        self.decryption_failed = True

        # If this is True, then we have not seen an advertisement with a payload
        # Until we see a payload, we can't tell if this device is encrypted or not
        self.pending = True

        # The last service_info we saw that had a payload
        # We keep this to help in reauth flows where we want to reprocess and old
        # value with a new bindkey.
        self.last_service_info: BluetoothServiceInfo | None = None

    def set_bindkey(self, bindkey: bytes | None) -> None:
        """Set the bindkey."""
        if bindkey:
            self.cipher: AESCCM | None = AESCCM(bindkey, tag_length=4)
        else:
            self.cipher = None
        self.bindkey = bindkey

    def supported(self, data: BluetoothServiceInfo) -> bool:
        if not super().supported(data):
            return False
        return True

    def _start_update(self, service_info: BluetoothServiceInfo) -> None:
        """Update from BLE advertisement data."""
        _LOGGER.debug("Parsing Xiaomi BLE advertisement data: %s", service_info)

        for uuid, data in service_info.service_data.items():
            if uuid == SERVICE_MIBEACON:
                if self._parse_xiaomi(service_info, service_info.name, data):
                    self.last_service_info = service_info

    def _parse_xiaomi(
        self, service_info: BluetoothServiceInfo, name: str, data: bytes
    ) -> bool:
        """Parser for Xiaomi sensors"""
        # check for adstruc length
        i = 5  # till Frame Counter
        msg_length = len(data)
        if msg_length < i:
            _LOGGER.debug("Invalid data length (initial check), adv: %s", data.hex())
            return False

        mac_readable = service_info.address
        source_mac = bytes.fromhex(mac_readable.replace(":", ""))

        # extract frame control bits
        frctrl = data[0] + (data[1] << 8)
        frctrl_mesh = (frctrl >> 7) & 1  # mesh device
        frctrl_version = frctrl >> 12  # version
        frctrl_auth_mode = (frctrl >> 10) & 3
        frctrl_solicited = (frctrl >> 9) & 1
        frctrl_registered = (frctrl >> 8) & 1
        frctrl_object_include = (frctrl >> 6) & 1
        frctrl_capability_include = (frctrl >> 5) & 1
        frctrl_mac_include = (frctrl >> 4) & 1  # check for MAC address in data
        frctrl_is_encrypted = (frctrl >> 3) & 1  # check for encryption being used
        frctrl_request_timing = frctrl & 1  # old version

        # Check that device is not of mesh type
        if frctrl_mesh != 0:
            _LOGGER.debug(
                "Device is a mesh type device, which is not supported. Data: %s",
                data.hex(),
            )
            return False

        # Check that version is 2 or higher
        if frctrl_version < 2:
            _LOGGER.debug(
                "Device is using old data format, which is not supported. Data: %s",
                data.hex(),
            )
            return False

        # Check that MAC in data is the same as the source MAC
        if frctrl_mac_include != 0:
            i += 6
            if msg_length < i:
                _LOGGER.debug("Invalid data length (in MAC check), adv: %s", data.hex())
                return False
            xiaomi_mac_reversed = data[5:11]
            xiaomi_mac = xiaomi_mac_reversed[::-1]
            if xiaomi_mac != source_mac:
                _LOGGER.debug(
                    "MAC address doesn't match data frame. Expected: %s, Got: %s",
                    to_mac(xiaomi_mac),
                    to_mac(source_mac),
                )
                return False
        else:
            xiaomi_mac = source_mac

        # determine the device type
        device_id = data[2] + (data[3] << 8)
        try:
            device = DEVICE_TYPES[device_id]
        except KeyError:
            _LOGGER.info(
                "BLE ADV from UNKNOWN Xiaomi device: MAC: %s, ADV: %s",
                source_mac,
                data.hex(),
            )
            _LOGGER.debug("Unknown Xiaomi device found. Data: %s", data.hex())
            return False

        device_type = device.model

        self.device_id = device_id
        self.device_type = device_type

        packet_id = data[4]

        sinfo = "MiVer: " + str(frctrl_version)
        sinfo += ", DevID: " + hex(device_id) + " : " + device_type
        sinfo += ", FnCnt: " + str(packet_id)
        if frctrl_request_timing != 0:
            sinfo += ", Request timing"
        if frctrl_registered != 0:
            sinfo += ", Registered and bound"
        else:
            sinfo += ", Not bound"
        if frctrl_solicited != 0:
            sinfo += ", Request APP to register and bind"
        if frctrl_auth_mode == 0:
            sinfo += ", Old version certification"
        elif frctrl_auth_mode == 1:
            sinfo += ", Safety certification"
        elif frctrl_auth_mode == 2:
            sinfo += ", Standard certification"

        # check for capability byte present
        if frctrl_capability_include != 0:
            i += 1
            if msg_length < i:
                _LOGGER.debug(
                    "Invalid data length (in capability check), adv: %s", data.hex()
                )
                return False
            capability_types = data[i - 1]
            sinfo += ", Capability: " + hex(capability_types)
            if (capability_types & 0x20) != 0:
                i += 1
                if msg_length < i:
                    _LOGGER.debug(
                        "Invalid data length (in capability type check), adv: %s",
                        data.hex(),
                    )
                    return False
                capability_io = data[i - 1]
                sinfo += ", IO: " + hex(capability_io)

        identifier = short_address(service_info.address)
        self.set_title(f"{device.name} {identifier} ({device.model})")
        self.set_device_name(f"{device.name} {identifier}")
        self.set_device_type(device.model)
        self.set_device_manufacturer(device.manufacturer)

        # check that data contains object
        if frctrl_object_include == 0:
            # data does not contain Object
            _LOGGER.debug("Advertisement doesn't contain payload, adv: %s", data.hex())
            return False

        self.pending = False

        # check for encryption
        if frctrl_is_encrypted != 0:
            sinfo += ", Encryption"
            payload = self._decrypt_mibeacon_v4_v5(data, i, xiaomi_mac)
        else:  # No encryption
            return False

        if payload is not None:
            sinfo += ", Object data: " + payload.hex()
            # loop through parse_xiaomi payload
            payload_start = 0
            payload_length = len(payload)
            # assume that the data may have several values of different types
            while payload_length >= payload_start + 3:
                obj_typecode = payload[payload_start] + (
                    payload[payload_start + 1] << 8
                )
                obj_length = payload[payload_start + 2]
                next_start = payload_start + 3 + obj_length
                if payload_length < next_start:
                    # The payload segments are corrupted - if this is legacy encryption
                    # then the key is probably just wrong
                    # V4/V5 encryption has an authentication tag, so we don't apply the
                    # same restriction there.
                    _LOGGER.debug(
                        "Invalid payload data length, payload: %s", payload.hex()
                    )
                    break
                this_start = payload_start + 3
                dobject = payload[this_start:next_start]
                if dobject and obj_length != 0:
                    resfunc = xiaomi_dataobject_dict.get(obj_typecode, None)
                    if resfunc:
                        self.unhandled.update(resfunc(dobject, self, device_type))
                    else:
                        _LOGGER.info(
                            "%s, UNKNOWN dataobject in payload! Adv: %s",
                            sinfo,
                            data.hex(),
                        )
                payload_start = next_start

        return True

    def _decrypt_mibeacon_v4_v5(
        self, data: bytes, i: int, xiaomi_mac: bytes
    ) -> bytes | None:
        """decrypt MiBeacon v4/v5 encrypted advertisements"""
        # check for minimum length of encrypted advertisement
        if len(data) < i + 9:
            _LOGGER.debug("Invalid data length (for decryption), adv: %s", data.hex())
            return None

        if not self.bindkey:
            self.bindkey_verified = False
            _LOGGER.debug("Encryption key not set and adv is encrypted")
            return None

        if not self.bindkey or len(self.bindkey) != 16:
            self.bindkey_verified = False
            _LOGGER.error("Encryption key should be 16 bytes (32 characters) long")
            return None

        nonce = b"".join([xiaomi_mac[::-1], data[2:5], data[-7:-4]])
        associated_data = b"\x11"
        mic = data[-4:]
        encrypted_payload = data[i:-7]

        assert self.cipher is not None  # nosec
        # decrypt the data
        try:
            decrypted_payload = self.cipher.decrypt(
                nonce, encrypted_payload + mic, associated_data
            )
        except InvalidTag as error:
            if self.decryption_failed is True:
                # we only ask for reautentification till
                # the decryption has failed twice.
                self.bindkey_verified = False
            else:
                self.decryption_failed = True
            _LOGGER.warning("Decryption failed: %s", error)
            _LOGGER.debug("mic: %s", mic.hex())
            _LOGGER.debug("nonce: %s", nonce.hex())
            _LOGGER.debug("encrypted payload: %s", encrypted_payload.hex())
            return None
        if decrypted_payload is None:
            self.bindkey_verified = False
            _LOGGER.error(
                "Decryption failed for %s, decrypted payload is None",
                to_mac(xiaomi_mac),
            )
            return None
        self.decryption_failed = False
        self.bindkey_verified = True
        print(f"decrypted payload: {decrypted_payload.hex()}")
        return decrypted_payload

    def add_entities(self, pd_id: int) -> None:
        """Add entities for all supported sensors."""
        device = DEVICE_TYPES[pd_id]
        for key in device.binary_sensor:
            device_key = DeviceKey(key, None)
            self._binary_sensor_descriptions_updates.setdefault(
                device_key,
                BinarySensorDescription(
                    device_class=key,
                    device_key=device_key,
                ),
            )
        for key in device.sensor:
            device_key = DeviceKey(key, None)
            self._sensor_descriptions_updates.setdefault(
                device_key,
                SensorDescription(
                    device_class=key,
                    device_key=device_key,
                    native_unit_of_measurement=None,
                ),
            )
