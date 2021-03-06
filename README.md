# Charge Amps for Home Assistant

This repository contains a [Charge Amps](https://charge-amps.com/) component for [Home Assistant](https://www.home-assistant.io/).

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs) [![travis_ci_badge](https://travis-ci.org/kirei/python-chargeamps.svg?branch=master)](https://travis-ci.org/kirei/python-chargeamps)

The module is developed by [Kirei AB](https://www.kirei.se) and is not supported by [Charge Amps AB](https://charge-amps.com).

## Installation

Installation via HACS by adding `https://github.com/kirei/hass-chargeamps` as a custom repository or by copying `custom_components/chargeamps`.

## Supported Hardware

- [Charge Amps AURA](https://charge-amps.com/products/charging-stations/aura/)
- [HALO Wallbox](https://charge-amps.com/products/charging-stations/halo-wallbox/)


## Configuration

The component requires configuration via the Home Assistant configuration file. The following parameters are required:

    chargeamps:
      username: EMAIL_ADDRESS
      password: SECRET_PASSWORD
      api_key: SECRET_API_KEY

The default is to configure all charge points for the account. To only include some charge points a list of charge point IDs can be provided using the `chargepoints` parameter.

N.B. You need an API key from [Charge Amps Support](mailto:support@charge-amps.com) to use this component.


## Entities

Each Chargeamps chargepoint connector will be represented as a sensor with the current status of the connector as the state. Each connector will also be represented as a switch that can be used to enable/disable the connector.


### Additional sensor attributes

- `total_consumption_kwh`

### Additional switch attributes

- `max_current`


## Services

The following services are implemented by the component:

- `set_light` -- set charge point lights
- `set_max_current` -- set max current for connector
- `enable` -- enable connector
- `disable` -- disable connector
