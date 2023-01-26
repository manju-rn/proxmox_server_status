# Proxmox Server Status is a Custom Integration for Home Assistant. It polls the configured Proxmox Server for the Nodes, it's details and hosted VMs and LXCs 

***Why was this created?***
    The existing integration in the Home Assistant Official Integration for Proxmox, there is no dynamic polling of the VMs and LXCs. One needs to manually provide the Nodes and its related VM / LXC IDs in the configuration. Based on the provided IDs, the integration ONLY fetchs the status of those Nodes and related VM / LXCs. This may be okay for few VM / LXCs but if a counts becomes higher or some VMs are removed or added, the configuration will need to be updated and Home Assistant restarted. Also, the only information that is fetched by the existing integration is the Status - when it is running or not.

    Proxmox Servers / Datacenter store vast amount of information regarding it's Host and all the VMs and LXCs it hosts. It also provides a API to fectch the same. This integration uses the same API to dynamically fetch the details of all the Nodes, it's VMs and LXCs. It can also display more details for those VMs and LXC - like memory used, max memory available, etc 

***Configuration that is needed:***
    This integration provides an Sensor entity. The following sensor configuration is required to be done in configuration.yaml (or sensor.yaml based on any split of the configruation one might have done)

```
    sensor:
    - platform: proxmox_server_status
        prox_entity_name: manju-prox-server
        prox_ip: !secret prox_ip
        prox_api_token: !secret prox_api_token
        prox_attr_seperator: ":"
```

***Config Details***
prox_entity_name: # Optional: Defines the entity that will be created in Home Assitant. defauls to platform name - proxmox_server_status
prox_ip: # Required: IP or Host name: Port  of the Proxmox server. Do not prefix or suffix anything example  192.168.0.1:8006
prox_api_token: # Required: API Token to be generated for a Proxmox server
prox_attr_seperator: # Optional: The VMs and LXCs are stored as attribute values in the sensor seperated by ,  This seperator could be overriden. This would help in any templating as may be required
