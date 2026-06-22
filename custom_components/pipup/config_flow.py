"""Config flow for PiPup (manual entry + zeroconf discovery)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import PipupClient, PipupError
from .const import DEFAULT_PORT, DOMAIN


class PipupConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PiPup."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise discovery state."""
        self._host: str | None = None
        self._port: int = DEFAULT_PORT
        self._name: str | None = None

    async def _async_status(
        self, host: str, port: int, token: str | None
    ) -> dict[str, Any]:
        """Return /status, proving the host is reachable and really is PiPup."""
        client = PipupClient(async_get_clientsession(self.hass), host, port, token)
        return await client.async_status()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            token = user_input.get(CONF_TOKEN) or None
            try:
                status = await self._async_status(host, port, token)
            except PipupError:
                errors["base"] = "cannot_connect"
            else:
                # Prefer the device's stable id; fall back to host:port.
                await self.async_set_unique_id(status.get("id") or f"{host}:{port}")
                self._abort_if_unique_id_configured(
                    updates={CONF_HOST: host, CONF_PORT: port}
                )
                return self.async_create_entry(
                    title=f"PiPup ({host})",
                    data={CONF_HOST: host, CONF_PORT: port, CONF_TOKEN: token},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=self._host or ""): str,
                vol.Required(CONF_PORT, default=self._port): int,
                vol.Optional(CONF_TOKEN): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle a TV discovered over mDNS (``_pipup._tcp``)."""
        host = discovery_info.host
        port = discovery_info.port or DEFAULT_PORT
        properties = discovery_info.properties

        # The app advertises a stable id and a friendly name as TXT records.
        await self.async_set_unique_id(properties.get("id") or f"{host}:{port}")
        self._abort_if_unique_id_configured(updates={CONF_HOST: host, CONF_PORT: port})

        self._host = host
        self._port = port
        self._name = properties.get("name") or host
        self.context["title_placeholders"] = {"name": f"PiPup {self._name}"}
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm adding a discovered TV (and optionally supply a token)."""
        assert self._host is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input.get(CONF_TOKEN) or None
            try:
                await self._async_status(self._host, self._port, token)
            except PipupError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"PiPup {self._name}",
                    data={
                        CONF_HOST: self._host,
                        CONF_PORT: self._port,
                        CONF_TOKEN: token,
                    },
                )

        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=vol.Schema({vol.Optional(CONF_TOKEN): str}),
            description_placeholders={"host": self._host},
            errors=errors,
        )
