# NetBox Baseline Environment

This script is designed to create all the objects within the NetBox environment ready for adding devices. It does not add the devices themselves. Its purpose to add objects rather than edit or delete existing objects. It is not idempotent.\
The Netbox environment is defined in YAML files that follows the hierarchical structure of the NetBox menus. The script is formatted to follow this same structure allowing sub-sections of the environment to be created or additions to be made to an existing section.

### API Engine

From the YAML input files per-object *Data-Models* are created that are fed into the API engine to create any objects that do not already exist.

[![](https://mermaid.ink/img/eyJjb2RlIjoiZ3JhcGggTFJcbkFbL2lucHV0IFlBTUwgZmlsZS9dLS0-Qnt7RGF0YSBNb2RlbCBNZXRob2R9fS0tPkMoW0NoZWNrIE1ldGhvZF0pLS0-RCgoQ3JlYXRlIE1ldGhvZCkpXG5cbiIsIm1lcm1haWQiOnsidGhlbWUiOiJkZWZhdWx0In0sInVwZGF0ZUVkaXRvciI6ZmFsc2V9)](https://mermaid-js.github.io/mermaid-live-editor/#/edit/eyJjb2RlIjoiZ3JhcGggTFJcbkFbL2lucHV0IFlBTUwgZmlsZS9dLS0-Qnt7RGF0YSBNb2RlbCBNZXRob2R9fS0tPkMoW0NoZWNrIE1ldGhvZF0pLS0-RCgoQ3JlYXRlIE1ldGhvZCkpXG5cbiIsIm1lcm1haWQiOnsidGhlbWUiOiJkZWZhdWx0In0sInVwZGF0ZUVkaXRvciI6ZmFsc2V9)

The *engine* method calls *obj_check* to verify whether an object already exists and uses *obj_create* (API engine) to create the NetBox objects and handle errors.

### Data Models

Each NetBox menu is represented by a separate data-model class (from *dm.py*) which are instantiated using dictionaries from the input YAML file to create a list of dictionaries for each of objects under that NetBox menu. These dictionaries are passed through the *nbox.engine* class (from *netbox.py*) that hold all the methods that interface with NetBox to check object existence and perform object creation.

All data-model classes are built in the same format consisting of *cr_xxx* methods to create object data-models and a *create_xxx* method to run all the *cr_xxx* methods and return the complete data-model. Below is an example of how Organsiation objects are created by first initialising the class (using input file dictionaries), then creating the data-model using the object engine method and finally checking for and creating the object by passing into the nbox.engine a Friendly name (for user message), path of api call, filter (to check if object already exists) and DM of data

``` python
org = Organisation(my_vars["tenant"], my_vars["rack_role"])
org_dict = org.create_tnt_site_rack()

nbox.engine("Rack Role", "dcim.rack_roles", "name", org_dict["rack_role"])
nbox.engine("Tenant", "tenancy.tenants", "name", org_dict["tnt"])
nbox.engine("Site", "dcim.sites", "name", org_dict["site"])
nbox.engine("Location (parent)", "dcim.locations", "slug", org_dict["prnt_loc"])
nbox.engine("Location (child)", "dcim.locations", "slug", org_dict["chld_loc"])
nbox.engine("Rack", "dcim.racks", "name", org_dict["rack"])
```

### Input file

The input data can be defined in the one file or split over multiple files of any name (script loads all files in a directory). Because of the hierarchical structure of the YAML file the mandatory dictionary elements will still be required in the file even if those objects are not being created by this script. For example, to create a rack the YAML file needs the tenant, site and location. Are two examples setups to show the struture.

**full_example:** An example setup with all the available options defined
**simple_example:** A more streamlined example with just the bare minimum options defined

Slug is optional, if not defined it is automatically generated from the name with any whitespaces replaced with _.

#### Organisation - *Tenants, Sites, Locations, Racks, Rack-roles*

Tenants are top of the tree with optional sites that contain locations (and child locations) that in turn contain racks.

| Object   | Description          | Mandatory | Optional |
| -------- | -------------------- | --------- | ---------|
| tenant   | List of tenants | name      | slug, descr, tags, ***site*** |
| tenant.site | List of sites | name     | slug, descr, time_zone, ASN, tags, ***location*** |
| tenant.site.location | List of locations (like a floor) | name | slug, descr, tags, ***rack***, ***location*** |
| tenant.site.location.rack | List of racks | name | role, height,tenant, tags
| tenant.site.location.location | List of child locations (like a room) | name | slug, descr, tags, ***rack*** |
| tenant.site.location.location.rack | List of racks in child locations | name | role, height, tenant, tags |
| rack-role| List of rack roles | name, color, | slug, descr, tags|

Be careful with child locations as if you are using a generic name such as *Room1* although is nested under the parent location in GUI need to make sure you define a unique slug.

#### Devices - *Manufacturers, Platforms, Device-types, Device-roles*

The device-types are built from pre-defined YAML files that can be downloaded from the NetBox community or custom created using that same format. By default these are expected to be in the *device_type* directory, *dvc_type_dir* can be used to change the location.
*https://github.com/netbox-community/devicetype-library*

| Object   | Description          | Mandatory | Optional |
| -------- | -------------------- | --------- | ---------|
| manufacturer | List of all device manufacturers | name | slug, descr, tags, ***platform*** |
| manufacturer.platform | List of platforms (used for NAPALM) | name | driver, slug, descr, tags |
| manufacturer.device_type | List of device-types (yaml files) | n/a | n/a |
| device_role | List of device roles | name, color | vm_role, slug, descr, tags |

#### IPAM - *RIR, Aggregates, Prefix/VLAN roles, VLAN-groups, VLANs, VRFs, Prefixes*
Prefix/VLAN roles group the VLANs and prefixes together to define environments. They are top of the IPAM hierarchy in the YAML file.\
VLAN-groups, VLANs, VRFs and prefixes are in some way related to sites and tenants. Tenants can be assigned in a hierarchical manner.\
Tags can be set in multiple places for VLANs, VRFs and prefixes with differing variants of inheritance.\
VRFs and prefixes are either defined under the role (non-VLAN environments like clouds) or the VLAN-group (if prefixes associated to VLANs).\






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
Site, tenant, cluster-group and tags can be set globally for all members of a cluster-type or be overridden on a per-cluster basis.

```css
vrt = nbox.create_vrt()
nbox.obj_check('Cluster Type', 'virtualization.cluster-types', 'name', vrt['cltr_type'])
nbox.obj_check('Cluster Group', 'virtualization.cluster-groups', 'name', vrt['cltr_grp'])
nbox.obj_check('Cluster', 'virtualization.clusters', 'name', vrt['cltr'])
```

## Installation and Prerequisites

Clone the repository and create a virtual environment

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
token = 'config.api_token'
os.environ['REQUESTS_CA_BUNDLE'] = '/Users/user1/Documents/nbox_py_scripts/myCA.pem'
```

The token is actually set in a separate `config.py` variable file that I *.gitignore* so as not to share the token with the rest of the world. This is imported with 'import config' so if you want to input the token directly in the script remove this line. All that *config.py* holds is a single token variable:

```bash
token = 'my_token_got_from_netbox'
```

## Usage

Before running ***nbox_env_setup.py*** it is recommended to use ***input_validate.py*** to verify the contents of input YAML file. It is an offline script (doesn't connect to NetBox) that verifies things such as:\
-All parent dictionaries (*tenant, manufacturer, rir, role, crt_type, provider, cluster_type*) are present and the key is a list (can be an empty list if not used)\
-All mandatory dictionaries are present\
-All Dictionary keys that are meant to be a list, integer, boolean or IPv4 address are of the correct format\
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


An example of a *check method*:

```python
nbox.obj_check('Tenant', 'tenancy.tenants', 'name', org['tnt'])
```

| Key    | Example | Description |
|-------------|-------|-------------|
| Object | *Tenant* | Friendly object name returned to stdout by the API call
| API Path | *tenancy.tenants* | URL-path used in the API call
| Attribute | *name* |  The key of the data model dictionary used to check if an object exists
| Data Model | *org['tnt']* |  The data model dictionary fed into the API engine

There are three possible outcomes from the *obj_create* API call which are relayed back in stdout:\
✅ Object created\
⚠️ Object already exists\
❌ Object can’t be created due to the defined error