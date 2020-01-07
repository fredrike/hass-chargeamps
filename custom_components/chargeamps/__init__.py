"""
Component to integrate with Chargeamps.

For more details about this component, please refer to
https://github.com/kirei/hass-chargeamps
"""

import logging
from datetime import timedelta
from typing import Optional

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from chargeamps.base import ChargePoint, ChargePointConnectorStatus
from chargeamps.external import ChargeAmpsExternalClient
from homeassistant import config_entries
from homeassistant.const import (CONF_API_KEY, CONF_PASSWORD, CONF_URL,
                                 CONF_USERNAME)
from homeassistant.helpers import discovery
from homeassistant.util import Throttle

from .const import CONF_CHARGEPOINTS, DOMAIN, DOMAIN_DATA, PLATFORMS

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_API_KEY): cv.string,
                vol.Optional(CONF_URL): cv.url,
                vol.Optional(CONF_CHARGEPOINTS): vol.All(cv.ensure_list, [cv.string]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_SERVICE_MAP = {
    "set_max_current": "async_set_max_current",
    "enable": "async_enable_ev",
    "disable": "async_disable_ev",
}


async def async_setup(hass, config):
    """Set up this component using YAML."""
    if config.get(DOMAIN) is None:
        # We get here if the integration is set up using config flow
        return True

    # Create DATA dict
    hass.data[DOMAIN_DATA] = {}

    # Get "global" configuration.
    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    api_key = config[DOMAIN].get(CONF_API_KEY)
    api_base_url = config[DOMAIN].get(CONF_URL)
    charge_point_ids = config[DOMAIN].get(CONF_CHARGEPOINTS)

    # Configure the client.
    client = ChargeAmpsExternalClient(email=username,
                                      password=password,
                                      api_key=api_key,
                                      api_base_url=api_base_url)

    # check all configured chargepoints or discover
    if charge_point_ids is not None:
        for cp_id in charge_point_ids:
            try:
                await client.get_chargepoint_status(cp_id)
                _LOGGER.info("Adding chargepoint %s", cp_id)
            except Exception:
                _LOGGER.error("Error adding chargepoint %s", cp_id)
        if len(charge_point_ids) == 0:
            _LOGGER.error("No chargepoints found")
            return False
    else:
        charge_point_ids = []
        for cp in await client.get_chargepoints():
            _LOGGER.info("Discovered chargepoint %s", cp.id)
            charge_point_ids.append(cp.id)

    handler = ChargeampsHandler(hass, client, charge_point_ids)
    hass.data[DOMAIN_DATA]["handler"] = handler
    hass.data[DOMAIN_DATA]["info"] = {}
    hass.data[DOMAIN_DATA]["chargepoint"] = {}
    hass.data[DOMAIN_DATA]["connector"] = {}
    await handler.update_info()

    # Register services to hass
    async def execute_service(call):
        function_name = _SERVICE_MAP[call.service]
        function_call = getattr(handler, function_name)
        await function_call(call.data)

    for service in _SERVICE_MAP:
        hass.services.async_register(DOMAIN, service, execute_service)

    # Load platforms
    for domain in PLATFORMS:
        hass.async_create_task(
            discovery.async_load_platform(hass, domain, DOMAIN, {}, config)
        )

    return True


class ChargeampsHandler:
    """This class handle communication and stores the data."""

    def __init__(self, hass, client, charge_point_ids):
        """Initialize the class."""
        self.hass = hass
        self.client = client
        self.charge_point_ids = charge_point_ids
        self.default_charge_point_id = charge_point_ids[0]
        self.default_connector_id = 1

    async def get_chargepoint_statuses(self):
        res = []
        for cp_id in self.charge_point_ids:
            res.append(await self.client.get_chargepoint_status(cp_id))
        return res

    def get_chargepoint_info(self, charge_point_id) -> ChargePoint:
        return self.hass.data[DOMAIN_DATA]["info"].get(charge_point_id)

    def get_connector_status(self, charge_point_id, connector_id) -> Optional[ChargePointConnectorStatus]:
        return self.hass.data[DOMAIN_DATA]["connector"].get((charge_point_id, connector_id))

    async def set_connector_mode(self, charge_point_id, connector_id, mode):
        settings = await self.client.get_chargepoint_connector_settings(charge_point_id, connector_id)
        settings.mode = mode
        _LOGGER.info("Setting chargepoint connector: %s", settings)
        await self.client.set_chargepoint_connector_settings(settings)

    async def set_connector_max_current(self, charge_point_id, connector_id, max_current):
        settings = await self.client.get_chargepoint_connector_settings(charge_point_id, connector_id)
        settings.max_current = max_current
        _LOGGER.info("Setting chargepoint connector: %s", settings)
        await self.client.set_chargepoint_connector_settings(settings)

    async def update_info(self):
        for cp in await self.client.get_chargepoints():
            if cp.id in self.charge_point_ids:
                self.hass.data[DOMAIN_DATA]["info"][cp.id] = cp
                _LOGGER.info("Update info for chargepoint %s", cp.id)
                _LOGGER.debug("INFO = %s", cp)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update_data(self, charge_point_id):
        """Update data."""
        try:
            _LOGGER.debug("Update data for chargepoint %s", charge_point_id)
            status = await self.client.get_chargepoint_status(charge_point_id)
            _LOGGER.debug("STATUS = %s", status)
            self.hass.data[DOMAIN_DATA]["chargepoint"][charge_point_id] = status
            for connector_status in status.connector_statuses:
                _LOGGER.debug("Update data for chargepoint %s connector %d", charge_point_id, connector_status.connector_id)
                self.hass.data[DOMAIN_DATA]["connector"][(charge_point_id, connector_status.connector_id)] = connector_status
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.error("Could not update data - %s", error)

    async def async_set_max_current(self, param):
        """Set current maximum in async way."""
        try:
            max_current = param["max_current"]
        except (KeyError, ValueError) as ex:
            _LOGGER.warning("Current value is not correct. %s", ex)
        charge_point_id = param.get("chargepoint", self.default_charge_point_id)
        connector_id = param.get("connector", self.default_connector_id)
        await self.set_connector_max_current(charge_point_id, connector_id, max_current)

    async def async_enable_ev(self, param):
        """Enable EV in async way."""
        charge_point_id = param.get("chargepoint", self.default_charge_point_id)
        connector_id = param.get("connector", self.default_connector_id)
        await self.set_connector_mode(charge_point_id, connector_id, "On")

    async def async_disable_ev(self, param=None):
        """Disable EV in async way."""
        charge_point_id = param.get("chargepoint", self.default_charge_point_id)
        connector_id = param.get("connector", self.default_connector_id)
        await self.set_connector_mode(charge_point_id, connector_id, "Off")
