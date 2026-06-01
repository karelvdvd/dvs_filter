import asyncio
import json
import logging

import aiohttp
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_URL
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

DEFAULT_URL = "ws://192.168.53.10:8080/ws"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_URL, default=DEFAULT_URL): cv.string,
})

SENSOR_KEYS = {
    "4": "Key 4",
    "5": "Key 5",
    "60": "Key 60",
    "61": "Key 61",
    "62": "Key 62",
    "63": "Key 63",
    "64": "Key 64",
    "65": "Key 65",
    "66": "Key 66",
    "67": "Key 67",
    "70": "Voltage",
    "120": "Key 120",
    "121": "Key 121",
    "122": "MAC",
    "123": "Status",
    "142": "Key 142",
    "143": "SMS status",
    "144": "Key 144",
}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    url = config[CONF_URL]
    hub = DVSFilterHub(hass, url)

    entities = [
        DVSFilterSensor(hub, key, name)
        for key, name in SENSOR_KEYS.items()
    ]

    async_add_entities(entities)

    hass.async_create_task(hub.connect())
    return True


class DVSFilterHub:
    def __init__(self, hass, url):
        self.hass = hass
        self.url = url
        self.data = {}
        self.listeners = []

    def register(self, callback):
        self.listeners.append(callback)

    async def connect(self):
        session = async_get_clientsession(self.hass)

        while True:
            try:
                _LOGGER.warning("Connecting to DVS filter websocket: %s", self.url)

                async with session.ws_connect(self.url, heartbeat=30) as ws:
                    _LOGGER.warning("Connected to DVS filter websocket")

                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            _LOGGER.debug("DVS raw data: %s", msg.data)

                            try:
                                self.data = json.loads(msg.data)

                                for callback in self.listeners:
                                    callback()

                            except Exception as err:
                                _LOGGER.error("Error parsing DVS data: %s", err)

                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            _LOGGER.warning("DVS websocket closed or error")
                            break

            except Exception as err:
                _LOGGER.warning("DVS websocket error: %r", err)

            _LOGGER.warning("Reconnecting to DVS filter websocket in 10 seconds")
            await asyncio.sleep(10)


class DVSFilterSensor(SensorEntity):
    def __init__(self, hub, key, name):
        self.hub = hub
        self.key = key
        self._attr_name = f"DVS Filter {name}"
        self._attr_unique_id = f"dvs_filter_{key}"
        self._attr_native_value = None

        self._attr_device_info = {
            "identifiers": {("dvs_filter", "dvs_filter_controller")},
            "name": "DVS Filter",
            "manufacturer": "DVS Filtertechniek",
            "model": "CL65-L Controller",
        }

        hub.register(self._update_callback)

    def _update_callback(self):
        self._attr_native_value = self.hub.data.get(self.key)
        self.schedule_update_ha_state()