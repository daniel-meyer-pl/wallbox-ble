"""Wallbox BLE API Client."""
from __future__ import annotations

import random
import asyncio
import json
import contextlib

from bleak import BleakClient
from bleak_retry_connector import establish_connection

from homeassistant.components.bluetooth import async_ble_device_from_address

from .const import LOGGER


class WallboxBLEApiConst:
    # Default (Pulsar Plus / "BgExpress" radio). Overridden at runtime once we
    # detect which BLE profile the connected charger actually exposes.
    UART_SERVICE_UUID = "331a36f5-2459-45ea-9d95-6142f0c4b307"
    UART_RX_CHAR_UUID = "a9da6040-0823-4995-94ec-9ce41ca28833"
    UART_TX_CHAR_UUID = "a73e9a10-628f-4494-a099-12efaf72258f"

    # Wallbox ships several BLE radio modules across hardware revisions, each
    # with its own GATT UUIDs but the SAME EaE+JSON application protocol (taken
    # from the official Android app, enum sr.b). "stream_mode" is the byte to
    # write to the mode characteristic to put the module into raw-stream mode so
    # writes to the RX characteristic are forwarded to the charger MCU (Zentri
    # modules need this; the Pulsar Plus does not).
    BLE_PROFILES = [
        {
            "name": "zentri",
            "service": "175f8f23-a570-49bd-9627-815a6a27de2a",
            "rx": "1cce1ea8-bd34-4813-a00a-c76e028fadcb",
            "tx": "cacc07ff-ffff-4c48-8fae-a9ef71b75e26",
            "mode": "20b9794f-da1a-4d14-8014-a0fb9cefb2f7",
            "stream_mode": 0x01,
        },
        {
            "name": "bgexpress",
            "service": "331a36f5-2459-45ea-9d95-6142f0c4b307",
            "rx": "a9da6040-0823-4995-94ec-9ce41ca28833",
            "tx": "a73e9a10-628f-4494-a099-12efaf72258f",
            "mode": "75a9f022-af03-4e41-b4bc-9de90a47d50b",
            "stream_mode": None,
        },
    ]

    GET_AUTOLOCK = "g_alo"
    GET_BATTERY_CONFIG = "r_socr"
    GET_CHARGER_VERSIONS = "fw_v_"
    GET_DISCHARGE_SESSION = "r_dis"
    GET_DYNAMIC_GRID_CODE = "ggcds"
    GET_DYNAMIC_GRID_CODE_REGULATIONS = "r_gcdl"
    GET_DYNAMIC_GRID_CODE_FEATURES = "r_gcdf"
    GET_DYNAMIC_GRID_CODE_LOGS = "r_gcli"
    GET_DYNAMIC_GRID_CODE_LOGS_DETAIL = "r_gcld"
    GET_DYNAMIC_GRID_CODE_LOGS_SIZE = "r_gcls"
    GET_DYNAMIC_GRID_CODE_ALERT = "r_gcai"
    GET_DYNAMIC_GRID_CODE_ALERT_SIZE = "r_gcas"
    GET_ECO_SMART_CONFIGURATION = "g_ecos"
    GET_GESTURE_CONFIGURATION = "ggsta"
    GET_GRID_CODE = "r_gcd"
    GET_HALO_CONFIG = "g_halocfg"
    GET_HOTSPOT_UPDATE_STATUS = "r_hup"
    GET_IP_MODE = "gimod"
    GET_LOCK_STATUS = "r_lck"
    GET_MAC_ADDRESSES = "g_mac"
    GET_MAX_AVAILABLE_CURRENT = "r_fsI"
    GET_MID_CONFIGURATION = "g_mid"
    GET_MOBILE_CONNECTIVITY = "gmcon"
    GET_NETWORKS_STATUS = "gnsta"
    GET_OCPP = "g_ocpp"
    GET_POWER_BOOST = "r_hsh"
    GET_POWER_BOOST_STATUS = "r_dca"
    GET_POWER_INFUSION = "g_pwi"
    GET_POWER_SHARING = "g_psh"
    GET_PROXY_MODE = "gpmod"
    GET_SCHEDULE = "r_sch"
    GET_SERIAL_NUMBER = "r_sn_"
    GET_SESSIONS_INFO = "r_ses"
    GET_SESSION = "r_log"
    GET_STATUS = "r_dat"
    GET_TIMEZONE = "g_tzn"
    GET_GROUNDING_STATUS = "r_wel"
    GET_WIFI_NETWORKS = "gwnet"
    GET_WIFI_STATUS = "gwsta"
    LOCK = "w_lck"
    REBOOT = "rebot"
    SET_AUTOLOCK = "s_alo"
    SET_BATTERY_CONFIG = "w_socr"
    SEND_TRANSACTION_DATA = "w_td"
    SET_DATA_TRANSACTION_STATUS = "s_dts"
    SET_DYNAMIC_GRID_CODE = "sgcds"
    SET_DYNAMIC_GRID_CODE_REGULATION = "w_gcdr"
    SET_DYNAMIC_GRID_CODE_FEATURE = "w_gcdf"
    SET_ECO_SMART_CONFIGURATION = "s_ecos"
    SET_GESTURE_CONFIGURATION = "sgsta"
    SET_GRID_CODE = "w_gcd"
    SET_HALO_CONFIG = "s_halocfg"
    SET_HOTSPOT_UPDATE = "s_hup"
    SET_HOTSPOT_UPDATE_INFO = "s_deb"
    SET_IP_MODE = "simod"
    SET_MAX_CHARGING_CURRENT = "w_mxI"
    SET_MID_CONFIGURATION = "s_mid"
    SET_MOBILE_CONNECTIVITY = "smcon"
    SET_MOBILE_CONNECTIVITY_STATUS = "smcen"
    SET_MULTIUSER = "s_mus"
    SET_OCPP = "s_ocpp"
    SET_POWER_BOOST = "w_hsh"
    SET_POWER_INFUSION = "s_pwi"
    SET_POWER_SHARING = "s_psh"
    SET_PROXY_MODE = "spmod"
    SET_SCHEDULE = "w_sch"
    SET_TIME = "Wtime"
    SET_TIMEZONE = "s_tzn"
    SET_USER = "suser"
    SET_USER_LIST = "sulis"
    SET_GROUNDING_STATUS = "w_wel"
    SET_WIFI = "swcon"
    SET_WIFI_STATUS = "swsta"
    SOFTWARE_CHECK = "gupdc"
    START_STOP_CHARGING = "w_cha"
    UNLOCK_MOBILE_SIM = "smpuk"
    UPDATE_SOFTWARE_PROGRESS = "supdp"
    UPDATE_SOFTWARE = "supds"

    STATUS_CODES = [
        "READY",  # 0
        "CHARGING",  # 1
        "CONNECTED_WAITING_CAR",  # 2
        "CONNECTED_WAITING_SCHEDULE",  # 3
        "PAUSED",  # 4
        "SCHEDULE_END",  # 5
        "LOCKED",  # 6
        "ERROR",  # 7
        "CONNECTED_WAITING_CURRENT_ASSIGNATION",  # 8
        "UNCONFIGURED_POWER_SHARING",  # 9
        "QUEUE_BY_POWER_BOOST",  # 10
        "DISCHARGING",  # 11
        "CONNECTED_WAITING_ADMIN_AUTH_FOR_MID",  # 12
        "CONNECTED_MID_SAFETY_MARGIN_EXCEEDED",  # 13
        "OCPP_UNAVAILABLE",  # 14
        "OCPP_CHARGE_FINISHING",  # 15
        "OCPP_RESERVED",  # 16
        "UPDATING",  # 17
        "QUEUE_BY_ECO_SMART",  # 18
    ]


class WallboxBLEApiClient:

    def detect_profile(self):
        """Pick the BLE profile (UUIDs) matching the services this charger exposes."""
        for profile in WallboxBLEApiConst.BLE_PROFILES:
            if self.client.services.get_service(profile["service"]) is not None:
                self.service_uuid = profile["service"]
                self.rx_uuid = profile["rx"]
                self.tx_uuid = profile["tx"]
                self.mode_uuid = profile["mode"]
                self.stream_mode = profile["stream_mode"]
                LOGGER.debug(f"Detected BLE profile '{profile['name']}' for {self.address}")
                return
        LOGGER.debug(f"No known BLE profile matched; using default UUIDs for {self.address}")

    async def authenticate(self):
        """Replicate the app's session login.

        The charger expects a SET_USER ("suser") command carrying its own user
        id before it accepts control commands. We read that id back from the
        status response (r_dat -> "usid"). No PIN/bonding is involved.
        """
        try:
            ok, data = await self.async_get_data()
            if ok and isinstance(data, dict) and data.get("usid") is not None:
                usid = data["usid"]
                ok2, _ = await self.request(WallboxBLEApiConst.SET_USER, usid)
                LOGGER.debug(f"Authenticated session with usid={usid} ok={ok2}")
            else:
                LOGGER.debug("No usid in status; skipping session auth")
        except Exception as e:
            LOGGER.debug(f"Authenticate failed: {e}")

    async def run_ble_client(self):
        async def callback_handler(sender, data):
            await self.rx_queue.put(data)

        disconnected_event = asyncio.Event()

        def disconnected_callback(client):
            LOGGER.debug("Disconnected!")
            disconnected_event.set()

        while True:
            LOGGER.debug("Connecting...")

            try:
                device = async_ble_device_from_address(self.hass, self.address, connectable=True)
                if not device:
                    raise Exception("No device found")
                # Use bleak_retry_connector so the connection is established
                # reliably AND all GATT services are fully resolved before we
                # try to use the UART characteristics (otherwise start_notify
                # fails with CharacteristicNotFound on a freshly connected link).
                self.client = await establish_connection(
                    BleakClient,
                    device,
                    self.address,
                    disconnected_callback=disconnected_callback,
                )
                LOGGER.debug("Connected!")
                # Detect which BLE radio profile this charger exposes and use
                # its UUIDs for the rest of the session.
                self.detect_profile()
                # IMPORTANT: replicate the exact order the official app uses, as
                # captured from a BLE HCI snoop. The charger does NOT use BLE
                # bonding/pairing; instead the command characteristic only
                # accepts writes once (1) notifications are enabled on the TX
                # characteristic and (2) the module has been switched to STREAM
                # mode. Doing these in the wrong order yields Write Not Permitted.
                # 1) enable notifications first
                await self.client.start_notify(self.tx_uuid, callback_handler)
                # 2) then switch the (Zentri) radio into raw STREAM mode
                if self.stream_mode is not None and self.mode_uuid:
                    try:
                        await self.client.write_gatt_char(self.mode_uuid, bytes([self.stream_mode]), True)
                        LOGGER.debug(f"Set stream mode {self.stream_mode} on {self.mode_uuid}")
                    except Exception as e:
                        LOGGER.debug(f"Failed to set stream mode: {e}")
                # 3) authenticate the session (charger expects "suser" with its
                # own user id, which we read back from r_dat) so that control
                # commands (lock, charge current, ...) are accepted.
                await self.authenticate()
                await disconnected_event.wait()
            except Exception as e:
                LOGGER.debug(f"Error: {type(e)}, {e}")
                await asyncio.sleep(1.0)
            finally:
                if self.client is not None:
                    with contextlib.suppress(Exception):
                        await self.client.disconnect()

            self.client = None
            disconnected_event.clear()

    async def connection_established(self):
        while True:
            if self.client and self.client.is_connected:
                return
            asyncio.sleep(0.1)

    @classmethod
    async def create(cls, hass, address):
        self = WallboxBLEApiClient()
        self.client = None
        # BLE profile UUIDs; default to the Pulsar Plus profile and refine once
        # connected via detect_profile().
        self.service_uuid = WallboxBLEApiConst.UART_SERVICE_UUID
        self.rx_uuid = WallboxBLEApiConst.UART_RX_CHAR_UUID
        self.tx_uuid = WallboxBLEApiConst.UART_TX_CHAR_UUID
        self.mode_uuid = None
        self.stream_mode = None
        self.rx_queue = asyncio.Queue()
        self.hass = hass
        self.address = address
        self.client_task = asyncio.create_task(self.run_ble_client())
        return self

    async def get_parsed_response(self, request_id):
        data = bytearray()
        while True:
            try:
                data += await self.rx_queue.get()
                parsed_data = json.loads(data)
                LOGGER.debug(f"Got {parsed_data=}")
                if parsed_data["id"] == request_id:
                    return parsed_data.get("r")
                else:
                    data = bytearray()
            except:
                pass

    def clear_rx_queue(self):
        self.rx_queue = asyncio.Queue()

    @property
    def ready(self):
        return self.client and self.client.is_connected

    async def request(self, method, parameter=None):
        if not self.ready:
            LOGGER.debug(f"NOT CONNECTED! {self.client}")
            return False, None

        request_id = random.randint(1, 999)

        uart_service = self.client.services.get_service(self.service_uuid)
        if uart_service is None:
            # Services not (yet) resolved - usually because pairing/bonding has
            # not completed. Avoid raising so the coordinator just reports the
            # device as unavailable instead of logging a traceback every poll.
            LOGGER.debug("UART service not found yet (not paired/resolved?)")
            return False, None
        rx_char = uart_service.get_characteristic(self.rx_uuid)

        payload = {"met": method, "par": parameter, "id": request_id}

        data = json.dumps(payload, separators=[",", ":"])
        data = bytes(data, "utf8")
        data = b"EaE" + bytes([len(data)]) + data
        data = data + bytes([sum(c for c in data) % 256])

        self.clear_rx_queue()
        try:
            # The charger's command characteristic is a raw UART stream that
            # only accepts small ATT writes; a single large write is rejected
            # with Write Not Permitted. The official app always splits the frame
            # into 20-byte chunks (it keeps the default 23-byte ATT MTU), so we
            # do the same regardless of the negotiated MTU.
            chunk = 20
            for i in range(0, len(data), chunk):
                await asyncio.wait_for(
                    self.client.write_gatt_char(rx_char, data[i:i + chunk], True), 2
                )
        except Exception as e:
            LOGGER.error(f"Failed to write to Bluetooth {e=}")
            return False, None

        try:
            response = await asyncio.wait_for(self.get_parsed_response(request_id), 2)
            LOGGER.debug("Got response!")
            return True, response
        except asyncio.TimeoutError:
            LOGGER.debug("No response!")
            return False, None

    async def async_get_data(self):
        """Get data from the API."""
        ok, data = await self.request(WallboxBLEApiConst.GET_STATUS)
        return ok, data

    async def async_set_locked(self, locked):
        """Get data from the API."""
        ok, _ = await self.request(WallboxBLEApiConst.LOCK, int(locked))
        return ok

    async def async_get_max_charge_current(self):
        """Get data from the API."""
        ok, data = await self.request(WallboxBLEApiConst.GET_MAX_AVAILABLE_CURRENT)
        return ok, data

    async def async_set_charge_current(self, current):
        """Get data from the API."""
        ok, _ = await self.request(WallboxBLEApiConst.SET_MAX_CHARGING_CURRENT, current)
        return ok
