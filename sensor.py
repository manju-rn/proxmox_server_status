"""Support for getting data from Proxmox Server."""
import asyncio
from datetime import timedelta
from zoneinfo import ZoneInfo
import logging
import json, datetime

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

""" Configuration params """
CONF_ATTRIBUTION = "Configuration for the proxmox nodes"
CONF_ENTITY_NAME = "prox_entity_name"                      # Desired Entity name to be created in HA
CONF_ENTITY_DEFAULT_NAME = "proxmox_server_status"
CONF_PROX_IP = "prox_ip"                                   # IP or Host of the Promox server to be monitored
CONF_PROX_APT_TOKEN = "prox_api_token"                     # API Token of the Proxmox server. The VM.Audit permissions is required
CONF_ATTR_SEPERATOR = "prox_attr_seperator"
ATTR_SEPERATOR = ","                                       # Default Attribute Seperator
CONF_ATTR_TZ = "prox_tz"                                   # Timezone of the Proxmox server. If not provided picks up the local HA's time

""" Params for the API Calls """
DEFAULT_RESOURCE_PREFIX_URL = "https://"                   # @TODO: Check ip prefix via lib and get rid of the prefix
HEADER_NAME_1 = "Authorization"
HEADER_NAME_2 = "Cookie"
HEADER_AUTH = "PVEAPIToken="                               # The suffic PVEAPITOKEN= is required along with the PVEAuthCookie @TODO: Move this to init?
HEADER_COOKIE = "PVEAuthCookie="                           # @TODO: Need to deal with the persistence of this Cookie
SSL_DEFAULT = False                                        # @TODO: Set the true as default and override from config, if provided

""" Promox API extensions to retrieve the data Ref: https://pve.proxmox.com/pve-docs/api-viewer/index.html """
PVE_URL_BASE = "/api2/json"                                # PVE BASE URL - Needs to be appended with the relevant URL suffixes to get sane data
PVE_URL_SUFFIX_ACCESS_TICKET = "/api2/json/access/ticket"  # PVE URL that returns a 2 hours limited time ticket. This ticker is to be passed during the API Calls. @TODO Should be keep a timer instead of passing this in every call?
PVE_URL_SUFFIX_NODES = "/nodes"                            # PVE URL that returns all the nodes, a ticket in the form of PVEAuthCookie needs to be passed 
PVE_URL_SUFFIX_VMS = "/qemu"                               # PVE URL append that returns all the VMs. This gives only the snapshot view not the gory details
PVE_URL_SUFFIX_LXC = "/lxc"                                # PVE URL append that returns all the LXCs. This gives only the snapshot view not the gory details
PVE_URL_SUFFIX_DETAIL_INFO = "/status/current"             # PVE URL append that when combined with VMs / LXCs provides the gory details  @TODO Should we fetch only the snapshot view in the initial api calls? The gory details could be seperate on-demand call

""" VM and LXC attribute key collection """
ATTR_KEYS = ['name', 'status',  'uptime', 'mem', 'maxmem', 'cpu', 'cpus', 'netin', 'netout', 'maxdisk']


# SCAN_INTERVAL = timedelta(minutes=480)                     # @TODO: make it configurable?
SCAN_INTERVAL = timedelta(seconds=60)

"""Validate the configuration data provided."""
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_ENTITY_NAME): cv.string,
    vol.Required(CONF_PROX_IP): cv.string,
    vol.Required(CONF_PROX_APT_TOKEN): cv.string,
    vol.Optional(CONF_ATTR_SEPERATOR): cv.string,
    vol.Optional(CONF_ATTR_TZ): cv.string,
})

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Proxmox sensors."""
    name = config.get(CONF_ENTITY_NAME)
    if name is None:
        name = CONF_ENTITY_DEFAULT_NAME
    _LOGGER.warn("Proxmox Server get Name %s", name)

    host = config.get(CONF_PROX_IP)
    token = config.get(CONF_PROX_APT_TOKEN)

    if config.get(CONF_ATTR_SEPERATOR) is not None :
        ATTR_SEPERATOR = CONF_ATTR_SEPERATOR

    session = async_get_clientsession(hass)
    async_add_entities([ProxmoxSensors(session, name, host, token)], True)


class ProxmoxSensors(Entity):
    """Representation of a Proxmox Sensors."""

    def __init__(self, session, name, host, token):
        """Initialize a ProxmoxSensor."""
        self._name = name
        self._url = DEFAULT_RESOURCE_PREFIX_URL + host
        self._token = token
        self._state = None
        self._session = session
        self._attrs = {ATTR_ATTRIBUTION: CONF_ATTRIBUTION}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        return self._attrs
    
    async def async_update(self):
        """Get the latest data from proxmox server and update the entities."""
        try:
            self._attrs = {}

            response = await self.fire_api_call(PVE_URL_SUFFIX_NODES)
            data = await response.text()

            if(data is not None):
                nodes_json = json.loads(data)
                nodes = nodes_json['data']
                _LOGGER.info("Proxmox extracted from Node JSON is %s", nodes)

                """ Extract the nodes """
                for node in nodes:
                    node_name = "/" + node['node']
                    response = await self.fire_api_call(PVE_URL_SUFFIX_NODES + node_name + PVE_URL_SUFFIX_VMS)
                    data = await response.text()
                    _LOGGER.info("Proxmox VMs data received from Node %s", data)
                    vms_json = json.loads(data)
                    vms =  vms_json['data']

                    """ Extract the VMs """
                    for vm in vms:
                        self.add_attributes(vm)
                        #self._attrs[vm['vmid']] = vm['name'] + ATTR_SEPERATOR + vm['status']
                        _LOGGER.warn("Proxmox extract VM Name %s %s %s %s %s", vm['vmid'] , ATTR_SEPERATOR ,  vm['name'] , ATTR_SEPERATOR , vm['status'])

                    response = await self.fire_api_call(PVE_URL_SUFFIX_NODES + node_name + PVE_URL_SUFFIX_LXC)
                    data = await response.text()
                    lxcs_json = json.loads(data)
                    lxcs =  lxcs_json['data']

                    """ Extract the LXCs """
                    for lxc in lxcs:
                        self.add_attributes(lxc)                        
                        # self._attrs[lxc['vmid']] = lxc['name'] + ATTR_SEPERATOR + lxc['status']
                        _LOGGER.warn("Proxmox extract LXC Name %s %s %s %s %s", lxc['vmid'] , ATTR_SEPERATOR , lxc['name'] , ATTR_SEPERATOR , lxc['status'])
            else:
                raise ValueError("Proxmox data received is Null") 

            message = "Updated - " + datetime.datetime.now(ZoneInfo('Asia/Singapore')).strftime('%d-%b-%y %H:%M:%S')
            # Update the State of the Sensor with the last updated time or Error, if it occurs
            self.state_update(message)            
        except (aiohttp.ClientError):
            message = "Error - Client Error"
            _LOGGER.error("Proxmox component Client Error from Proxmox server: " + aiohttp.ClientError)
            return
        except (asyncio.TimeoutError):
            message = "Error - Timeout Error"
            _LOGGER.error("Proxmox server connectivity timed out : " + self._url)
            return            
        except IndexError:
            message = "Error - JSON Parsing Error"
            _LOGGER.error("Proxmox - parsing error - Unable to extract data from response")
            return
        except ValueError as ve:
            message = "Error - ValueError"
            _LOGGER.error(ve)
            return
        
    async def fire_api_call(self, call_type):
        headers = {}  # Defines a Dict
        headers[HEADER_NAME_1] = HEADER_AUTH + self._token
        final_url = self._url + PVE_URL_BASE + call_type
        _LOGGER.info("Proxmox url triggering now is %s", final_url)
        with async_timeout.timeout(20):
            response = await self._session.get(final_url, headers=headers, ssl=SSL_DEFAULT)  # @TODO: Make the SSL_DEFAULT as true?

        _LOGGER.info("Proxmox Server Response  %s", response.status)
        return response
    
    def add_attributes(self, device):
        combined_attr_value = ""
        for ATTR_KEY in ATTR_KEYS:
            combined_attr_value = combined_attr_value + str(device[ATTR_KEY]) + ATTR_SEPERATOR

        self._attrs[device['vmid']] = combined_attr_value

    def state_update(self, message):
        self._state = message
