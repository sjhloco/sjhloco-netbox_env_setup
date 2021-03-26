# NetBox Baseline Environment

This script is designed to create all the objects within the NetBox environment ready for adding devices. It does not add the devices themselves. Its purpose to add objects rather than edit or delete existing objects. It is not idempotent.\
The Netbox environment is defined in a YAML file that follows the hierarchical structure of the NetBox menus. The script is formated to follow this same structure allowing subsections of the environment to be created or additions to be made to an existing section.

### API Engine

From the YAML input file per-object *Data-Models* are created that are fed into the API engine to create any objects that do not already exist.

[![](https://mermaid.ink/img/eyJjb2RlIjoiZ3JhcGggTFJcbkFbL2lucHV0IFlBTUwgZmlsZS9dLS0-Qnt7RGF0YSBNb2RlbCBNZXRob2R9fS0tPkMoW0NoZWNrIE1ldGhvZF0pLS0-RCgoQ3JlYXRlIE1ldGhvZCkpXG5cbiIsIm1lcm1haWQiOnsidGhlbWUiOiJkZWZhdWx0In0sInVwZGF0ZUVkaXRvciI6ZmFsc2V9)](https://mermaid-js.github.io/mermaid-live-editor/#/edit/eyJjb2RlIjoiZ3JhcGggTFJcbkFbL2lucHV0IFlBTUwgZmlsZS9dLS0-Qnt7RGF0YSBNb2RlbCBNZXRob2R9fS0tPkMoW0NoZWNrIE1ldGhvZF0pLS0-RCgoQ3JlYXRlIE1ldGhvZCkpXG5cbiIsIm1lcm1haWQiOnsidGhlbWUiOiJkZWZhdWx0In0sInVwZGF0ZUVkaXRvciI6ZmFsc2V9)

Before the object is created the *check method* is called to verify whether the object already exists. This method can be different dependant on the object (due to the DM hierarchy) whereas the same *create method* (API engine) is run for the creation of all objects.

***obj_check:*** Used for checking the existence of the majority of NetBox objects\
***dev_type_create:*** Used for checking the existence of device-types and their nested components (interfaces, PSUs, etc)\
***vlan_vrf_check:*** Used for checking the existence of VLANs and prefixes within VLAN-groups and VRFs

An example of a *check method*:

```css
nbox.obj_check('Tenant', 'tenancy.tenants', 'name', org['tnt'])
```

| Key    | Example | Description |
|-------------|-------|-------------|
| Object | *Tenant* | Friendly object name returned to stdout by the API call
| API Path | *tenancy.tenants* | URL-path used in the API call
| Attribute | *name* |  The key of the data model dictionary used to check if an object exists
| Data Model | *org['tnt']* |  The data model dictionary fed into the API engine

***obj_create:*** The API engine (is run by the check method) used to create NetBox objects and handle errors. 

There are three possible outcomes from the API call which are relayed back in stdout:\
✅ Object created\
⚠️ Object already exists\
❌ Object can’t be created due to the defined error

### Data Models

Each NetBox menu is represented by a seperate data model method. When instantiated they use the input YAML file to create a list of dictionaries for each of objects under that NetBox menu. These dictionaires are run through check methods to create the NetBox objects.\
Any of the check methods can be hashed out if the objects are not required. Because of the hierarchical structure of the YAML file the mandatory dictionary elements mwill still be required in the file even if those objects are not being created by this script. For example, to create a rack the YAML file needs the tenant, site and rack-group.

***full_example.yaml*** is an example input file with all the available options defined.\
***simple_example.yaml*** is a more streamlined example with just the bare minimum of options defined.

**Organisation:** *Tenants, sites, Rack-groups, Racks, Rack-roles*\
Tenants are top of the tree with optional sites that contain rack-groups that in turn contain racks.

```css
org = nbox.create_org_tnt_site_rack()
nbox.obj_check('Rack Role', 'dcim.rack_roles', 'name', org['rack_role'])
nbox.obj_check('Tenant', 'tenancy.tenants', 'name', org['tnt'])
nbox.obj_check('Site', 'dcim.sites', 'name', org['site'])
nbox.obj_check('Rack-group', 'dcim.rack_groups', 'name', org['rack_grp'])
nbox.obj_check('Rack', 'dcim.racks', 'name', org['rack'])
```

**Devices:** *Manufacturers, Platforms, Device-types, Device-roles*\
The device-types are built from pre-defined YAML files that can be downloaded from the NetBox community or custom created using that same format. By default these are expected to be in the *device_type* directory, *dvc_type_dir* can be used to change the location.
*https://github.com/netbox-community/devicetype-library*

```css
dvc = nbox.create_dvc_type_role()
nbox.obj_check('Device-role', 'dcim.device_roles', 'name', dvc['dev_role'])
nbox.obj_check('Manufacturer', 'dcim.manufacturers', 'name', dvc['mftr'])
nbox.obj_check('Platform', 'dcim.platforms', 'name', dvc['pltm'])
nbox.obj_check('Device-type', 'dcim.device_types', 'model', dvc['dev_type'])
```

**IPAM:** *RIR, Aggregates, Prefix/VLAN roles, VLAN-groups, VLANs, VRFs, Prefixes*\
Prefix/VLAN roles group the VLANs and prefixes together to define envirnoments. They are top of the IPAM hierachy in the YAML file.\
VLAN-groups, VLANs, VRFs and prefixes are in some way related to sites and tenants. Tenants can be assigned in a hierachical manner.\
Tags can be set in multiple places for VLANs, VRFs and prefixes with differing variantes of inheritance.\
VRFs and prefixes are either defined under the role (non-VLAN enviroments like clouds) or the VLAN-group (if prefixes associated to VLANs).\

```css
ipam = nbox.create_ipam()
nbox.obj_check('RIRs', 'ipam.rirs', 'name', ipam['rir'])
nbox.obj_check('Aggregates', 'ipam.aggregates', 'prefix', ipam['aggr'])
nbox.obj_check('Prefix/VLAN Role', 'ipam.roles', 'name', ipam['role'])
nbox.obj_check('VLAN Group', 'ipam.vlan-groups', 'name', ipam['vlan_grp'])
nbox.obj_check('VRF', 'ipam.vrfs', 'name', ipam['vrf'])
nbox.vlan_vrf_check('VLAN', ['ipam.vlans', 'ipam.vlan_groups'], ['name', 'group'], ipam['vlan'])
nbox.vlan_vrf_check('Prefix', ['ipam.prefixes', 'ipam.vrfs'], ['prefix', 'vrf'], ipam['prefix'])
```

**Provider:** *Circuit-type, Provider, Circuit*\
Providers are the ISPs that hold individual circuits with pre-defined circuit-types

```css
crt = nbox.create_crt()
# Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
nbox.obj_check('Circuit Type', 'circuits.circuit-types', 'name', crt['crt_type'])
nbox.obj_check('Provider', 'circuits.providers', 'name', crt['pvdr'])
nbox.obj_check('Circuit', 'circuits.circuits', 'cid', crt['crt'])
```

**Virtual:** *Cluster-group, Cluster-type, Cluster*\
Clusters are groupings of resources which VMs run within. Cluster-groups and types allow further grouping of clusters based on things such as location or technology.\
Site, tenant, cluster-group and tags can be set globally for all members of a cluster-type or be overiddern on a per-cluster basis.

```css
vrt = nbox.create_vrt()
nbox.obj_check('Cluster Type', 'virtualization.cluster-types', 'name', vrt['cltr_type'])
nbox.obj_check('Cluster Group', 'virtualization.cluster-groups', 'name', vrt['cltr_grp'])
nbox.obj_check('Cluster', 'virtualization.clusters', 'name', vrt['cltr'])
```

## Installation and Prerequisites

Clone the repostitary and create a virtual environoment

```css
git clone https://github.com/sjhloco/nbox_env.git
mkdir venv_nbox
python3 -m venv mkdir venv_nbox
source venv_nbox/bin/activate
```

Install the required packages (*PyYAML*, *pynetbox* and *rich*)

```bash
pip install -r requirements.txt
```

The first section of the script holds the customisable values to define the device-type template directory and NetBox API details.

```bash
dvc_type_dir = os.path.expanduser('/Users/user1/Documents/Coding/Netbox/nbox_py_scripts/nbox_env_setup/device_type')

netbox_url = "https://x.x.x.x"
token = 'my_token_got_from_netbox'
os.environ['REQUESTS_CA_BUNDLE'] = '/Users/user1/Documents/nbox_py_scripts/myCA.pem'
```

## Usage

Before running ***nbox_env_setup.py*** it is recommended to use ***input_validate.py*** to verify the contents of input YAML file. It is an offline script (doesnt connect to NetBox) that verifies things such as:\
-All parent dictionaries (*tenant, manufacturer, rir, role, crt_type, provider, cluster_type*) are present and the key is a list (can be an empty list if not used)\
-All mandatory dictionaires are present\
-All Dictionary keys that are meant to be a list, integrar, boolean or IPv4 address are of the correct format\
-All referenced objects such as tenant, site, rack_role, etc, exist within the input file\
-No duplicate object names

A test input file called *test_validate.yml* will trigger the majority of these formatting errors.

```bash
python input_validate.py test.yml
```

Once happy the format of the input file is correct run *nbox_env_setup.py* against the input file to build NetBox environment.

```bash
python nbox_env_setup.py simple_example.yml
```
