"""Sensor platform for Chargeamps."""

import logging

from homeassistant.const import DEVICE_CLASS_POWER, POWER_WATT
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, DOMAIN_DATA, ICON

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None
):  # pylint: disable=unused-argument
    """Setup sensor platform."""
    sensors = []
    handler = hass.data[DOMAIN_DATA]["handler"]
    for cp_id in handler.charge_point_ids:
        cp_info = handler.get_chargepoint_info(cp_id)
        sensors.append(
            ChargeampsTotalEnergy(hass, f"{cp_info.name}_{cp_id}_total_energy", cp_id,)
        )
        for connector in cp_info.connectors:
            sensors.append(
                ChargeampsSensor(
                    hass,
                    f"{cp_info.name}_{connector.charge_point_id}_{connector.connector_id}",
                    connector.charge_point_id,
                    connector.connector_id,
                )
            )
            sensors.append(
                ChargeampsPowerSensor(
                    hass,
                    f"{cp_info.name} {connector.charge_point_id} {connector.connector_id} Power",
                    connector.charge_point_id,
                    connector.connector_id,
                )
            )
            _LOGGER.info(
                "Adding chargepoint %s connector %s",
                connector.charge_point_id,
                connector.connector_id,
            )
    async_add_entities(sensors, True)


class ChargeampsEntity(Entity):
    """Chargeamps Entity class."""

    def __init__(self, hass, name, charge_point_id, connector_id):
        self.hass = hass
        self.charge_point_id = charge_point_id
        self.connector_id = connector_id
        self.handler = self.hass.data[DOMAIN_DATA]["handler"]
        self._name = name
        self._state = None
        self._attributes = {}
        self._interviewed = False

    async def interview(self):
        chargepoint_info = self.handler.get_chargepoint_info(self.charge_point_id)
        connector_info = self.handler.get_connector_info(
            self.charge_point_id, self.connector_id
        )
        self._attributes["chargepoint_type"] = chargepoint_info.type
        self._attributes["connector_type"] = connector_info.type
        self._interviewed = True

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return self._attributes

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        return f"{DOMAIN}_{self.charge_point_id}_{self.connector_id}"


class ChargeampsSensor(ChargeampsEntity):
    """Chargeamps Sensor class."""

    def __init__(self, hass, name, charge_point_id, connector_id):
        super().__init__(self, hass, name, charge_point_id, connector_id)
        self._icon = ICON

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    async def async_update(self):
        """Update the sensor."""
        _LOGGER.debug(
            "Update chargepoint %s connector %s",
            self.charge_point_id,
            self.connector_id,
        )
        await self.handler.update_data(self.charge_point_id)
        _LOGGER.debug(
            "Finished update chargepoint %s connector %s",
            self.charge_point_id,
            self.connector_id,
        )
        status = self.handler.get_connector_status(
            self.charge_point_id, self.connector_id
        )
        if status is None:
            return
        self._state = status.status
        self._attributes["total_consumption_kwh"] = round(
            status.total_consumption_kwh, 3
        )
        if not self._interviewed:
            await self.interview()


class ChargeampsTotalEnergy(ChargeampsEntity):
    """Chargeamps Total Energy class."""

    def __init__(self, hass, name, charge_point_id):
        super().__init__(self, hass, name, charge_point_id, "total_energy")

    async def async_update(self):
        """Update the sensor."""
        _LOGGER.debug(
            "Update chargepoint %s", self.charge_point_id,
        )
        await self.handler.update_data(self.charge_point_id)
        self._state = self.handler.get_chargepoint_total_energy(self.charge_point_id)
        _LOGGER.debug(
            "Finished update chargepoint %s", self.charge_point_id,
        )

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "kWh"


class ChargeampsPowerSensor(ChargeampsEntity):
    """Chargeamps Power Sensor class."""

    async def async_update(self):
        """Update the sensor."""
        _LOGGER.debug(
            "Update chargepoint %s connector %s",
            self.charge_point_id,
            self.connector_id,
        )
        await self.handler.update_data(self.charge_point_id)
        _LOGGER.debug(
            "Finished update chargepoint %s connector %s",
            self.charge_point_id,
            self.connector_id,
        )
        measurements = self.handler.get_connector_measurements(
            self.charge_point_id, self.connector_id
        )
        if measurements:
            self._state = round(
                sum([phase.current * phase.voltage for phase in measurements]), 0
            )
            self._attributes["active_phase"] = " ".join(
                [i.phase for i in measurements if i.current > 0]
            )
            for measure in measurements:
                self._attributes[f"{measure.phase.lower()}_power"] = round(
                    measure.voltage * measure.current, 0
                )
                self._attributes[f"{measure.phase.lower()}_current"] = round(
                    measure.current, 1
                )
        else:
            self._attributes["active_phase"] = ""
            for phase in range(1, 4):
                for measure in ("power", "current"):
                    self._attributes[f"L{phase.lower()}_{measure}"] = 0
            self._state = 0

    @property
    def unique_id(self):
        """Return a unique ID to use for this sensor."""
        return f"{super().unique_id}_power"

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_POWER

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return POWER_WATT
