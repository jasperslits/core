"""Config flow to configure roomba component."""
from roombapy import Roomba, RoombaDiscovery
from roombapy.getpassword import RoombaPassword
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import callback

from . import CannotConnect, async_connect_or_timeout, async_disconnect_or_timeout
from .const import (
    CONF_BLID,
    CONF_CONTINUOUS,
    CONF_DELAY,
    CONF_NAME,
    DEFAULT_CONTINUOUS,
    DEFAULT_DELAY,
    ROOMBA_SESSION,
)
from .const import DOMAIN  # pylint:disable=unused-import

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_CONTINUOUS, default=DEFAULT_CONTINUOUS): bool,
        vol.Optional(CONF_DELAY, default=DEFAULT_DELAY): int,
    }
)


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    roomba = Roomba(
        address=data[CONF_HOST],
        blid=data[CONF_BLID],
        password=data[CONF_PASSWORD],
        continuous=data[CONF_CONTINUOUS],
        delay=data[CONF_DELAY],
    )

    info = await async_connect_or_timeout(hass, roomba)

    return {
        ROOMBA_SESSION: info[ROOMBA_SESSION],
        CONF_NAME: info[CONF_NAME],
        CONF_HOST: data[CONF_HOST],
    }


class RoombaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Roomba configuration flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return RoombaFlowHandler(config_entry)

    async def async_step_import(self, import_info):
        """Set the config entry up from yaml."""
        return await self.async_step_user(import_info)

    async def async_step_link(self, user_input=None):
        """Attempt to link with the Hue bridge.

        Given a configured host, will ask the user to press the link button
        to connect to the bridge.
        """

        if user_input is None:
            return self.async_show_form(step_id="link")

        errors = {}

        user_input[CONF_HOST] = self.host
        user_input[CONF_CONTINUOUS] = self.continuous
        user_input[CONF_DELAY] = self.delay

        res = RoombaPassword(self.host).get_password()
        if res:
            user_input[CONF_PASSWORD] = res

            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
        else:
            errors["base"] = "cannot_read_password"

        if "base" not in errors:
            await async_disconnect_or_timeout(self.hass, info[ROOMBA_SESSION])
            return self.async_create_entry(title=info[CONF_NAME], data=user_input)

        if errors:
            return self.async_show_form(step_id="link", errors=errors)

    async def roomba_discover_robot(self):
        """Discover new devices."""
        roombadisco = RoombaDiscovery()
        if roombadisco:
            for robot in roombadisco.find():
                """ Check against configured devices """
                return {"ip": robot.ip, "blid": robot.blid}
        return None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            self.delay = user_input[CONF_DELAY]
            self.continuous = user_input[CONF_CONTINUOUS]

            return await self.async_step_link()

        discovered_robot = await self.roomba_discover_robot()
        if discovered_robot is None:
            errors["base"] = "no_discovery"
        else:
            self.host = discovered_robot["ip"]
            self.blid = discovered_robot["blid"]

        roomba_schema = vol.Schema(
            {
                vol.Optional(CONF_CONTINUOUS, default=DEFAULT_CONTINUOUS): bool,
                vol.Optional(CONF_DELAY, default=DEFAULT_DELAY): int,
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=roomba_schema, errors=errors
        )


class RoombaFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.host = None
        self.delay = None
        self.mode = None

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_CONTINUOUS,
                        default=self.config_entry.options.get(
                            CONF_CONTINUOUS, DEFAULT_CONTINUOUS
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_DELAY,
                        default=self.config_entry.options.get(
                            CONF_DELAY, DEFAULT_DELAY
                        ),
                    ): int,
                }
            ),
        )
