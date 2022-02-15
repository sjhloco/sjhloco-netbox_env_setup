# NetBox Baseline Environment

This script will create all the objects within the NetBox environment ready for the addition of devices, it does not add the devices themselves. It is not idempotent as the purpose is to add objects rather than edit or delete existing objects. The Netbox environment is defined in YAML files that follow the hierarchical structure of the NetBox menus. The script follows this same structure allowing sub-sections of the environment to be created or additions to be made to an existing section.

## API Engine

From the YAML input files per-object *Data-Models* are built and fed into the API engine to create any objects that do not already exist.

[![](https://mermaid.ink/img/eyJjb2RlIjoiZ3JhcGggTFJcbkFbL2lucHV0IFlBTUwgZmlsZS9dLS0-Qnt7RGF0YSBNb2RlbCBNZXRob2R9fS0tPkMoW0NoZWNrIE1ldGhvZF0pLS0-RCgoQ3JlYXRlIE1ldGhvZCkpXG5cbiIsIm1lcm1haWQiOnsidGhlbWUiOiJkZWZhdWx0In0sInVwZGF0ZUVkaXRvciI6ZmFsc2V9)](https://mermaid-js.github.io/mermaid-live-editor/#/edit/eyJjb2RlIjoiZ3JhcGggTFJcbkFbL2lucHV0IFlBTUwgZmlsZS9dLS0-Qnt7RGF0YSBNb2RlbCBNZXRob2R9fS0tPkMoW0NoZWNrIE1ldGhvZF0pLS0-RCgoQ3JlYXRlIE1ldGhvZCkpXG5cbiIsIm1lcm1haWQiOnsidGhlbWUiOiJkZWZhdWx0In0sInVwZGF0ZUVkaXRvciI6ZmFsc2V9)

The *obj_check* method verifies whether an object already exists and uses *obj_create* (API engine) to create the NetBox objects and handle errors.

## Data Models

Each NetBox menu is represented by a separate data-model class (from *dm.py*) that is instantiated using dictionaries from the input file to create a list of dictionaries for each of the objects under that NetBox menu. These dictionaries are passed through the *engine* class (from *netbox.py*) which hold all the methods that interact with NetBox to check object existence and perform object creation.

All data-model classes are built in the same format consisting of *cr_xxx* methods to create object data-models and a *create_xxx* method to run all the *cr_xxx* methods and return the complete data-model. Below is an example of how *Organisation* objects are created by first instantiating the class using input file dictionaries (*Organisation(xx)*), creating the data-model (*org.create(xx)*) and finally checking for and creating the objects (*nbox.engine(xx)*). A Friendly name (for user message), path of api call, filter (to check if object already exists) and data-model are passed into the engine.

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

## Input data

The input data can be defined in the one file or split over multiple files of any name (script loads all files in a directory). Because of the hierarchical structure of the YAML file the mandatory dictionary elements will still be required in the file even if those objects are not being created by this script. For example, to create a rack the YAML file needs the tenant, site and location. The structure can be found in the two example setups within the repo.

**full_example:** *An example setup with all the available options defined*\
**simple_example:** *A more streamlined example with just the bare minimum options defined*

For most options the slug is optional and if not defined will be automatically generated from the name replacing any whitespaces with _.

### Organisation - *Tenants, Sites, Locations, Racks, Rack-roles*

Tenants are top of the tree with optional sites that contain locations (and child locations) that in turn contain racks.

| Object   | Description          | Mandatory | Optional |
| -------- | -------------------- | --------- | ---------|
| tenant   | List of tenants | name      | slug, descr, tags, ***site*** |
| tenant.site | List of sites | name     | slug, descr, tags, time_zone, ASN,  ***location*** |
| tenant.site.location | List of locations (like a floor) | name | slug, descr, tags, ***rack***, ***location*** |
| tenant.site.location.rack | List of racks | name | tags, role, height, tenant
| tenant.site.location.location | List of child locations (like a room) | name | slug, descr, tags, ***rack*** |
| tenant.site.location.location.rack | List of racks in child locations | name | tags, role, height, tenant |
| rack-role | List of rack roles | name, color, | slug, descr, tags|

Be careful with child locations as if you are using a generic name such as *Room1* although it is nested under the parent location in GUI you need to make sure you define a unique slug as under the hood is no hierarchy.

### Devices - *Manufacturers, Platforms, Device-types, Device-roles*

The device-types are built from pre-defined YAML files that can be downloaded from the [NetBox community](https://github.com/netbox-community/devicetype-library) or custom created using that same format. By default these are expected to be stored in the *device_type* directory.

| Object   | Description          | Mandatory | Optional |
| -------- | -------------------- | --------- | ---------|
| manufacturer | List of all device manufacturers | name | slug, descr, tags, ***platform*** |
| manufacturer.platform | List of platforms (used for NAPALM) | name | slug, descr, tags, driver |
| manufacturer.device_type | List of device-type yaml files | n/a | n/a |
| device_role | List of device roles (to assign to device types) | name, color | slug, descr, tags, vm_role |

### IPAM - *RIR, Aggregates, Prefix/VLAN roles, VLAN groups, VLANs, VRFs, Prefixes*

Prefix/VLAN roles are at the top of the IPAM hierarchy in the YAML file grouping VLANs and prefixes together to define an environment.
VLAN-groups, VLANs, VRFs and prefixes are in some way related to sites and tenants. They are defined under the site with the sites tenant automatically associated unless overridden on a VLAN-group/VLAN/VRF/prefix basis.

VRFs and prefixes are either defined under the role (non-VLAN environments like clouds) or the VLAN group (sites with VLANs, prefixes can be associated to VLANs).

| Object   | Description          | Mandatory | Optional |
| -------- | -------------------- | --------- | ---------|
| rir      | List of governing bodies (includes RFC1918) | name | slug, descr, tags, is_private, ***aggregate*** |
| rir.aggregate | List of aggregates in the RIR (your assigned PA or PI prefixes) | prefix | descr, tags |
| role |  List of prefix and VLAN roles | name, ***site***  |  slug, descr, tags |
| role.site | List of existing sites to associate VLANs, VRFs and prefixes | name | ***vlan_grp***, ***vrf***
| role.site.vlan_grp | List of VLAN groups | name, ***vlan*** | slug, descr, tags, tenant, ***vrf***
| role.site.vlan_grp.vlan | List of VLANs in the VLAN group| name, id | descr, tags, tenant
| role.site.vlan_grp.vrf | VRFs in a site with VLANs (prefixes can be linked to VLANs) | name, ***prefix*** | descr, tags, rd, import_rt, export_rt, unique, tenant
| role.site.vlan_grp.vrf.prefix | List of prefixes within this VRF | pfx | descr, tags, vl, pool, tenant
| role.site.vrf | VRFs whose prefixes arent associated to VLANs | name, ***prefix*** | descr, tags, rd, import_rt, export_rt, unique, tenant
| role.site.vrf.prefix | List of prefixes within this VRF | pfx | descr, tags, pool, tenant

### Provider/ Circuit -  *Circuit-type, Provider, Circuit*

Providers are the ISPs that hold individual circuits with pre-defined circuit-types.

| Object   | Description          | Mandatory | Optional |
| -------- | -------------------- | --------- | ---------|
| circuit_type | List of circuit types | name | slug, descr, tags
| provider | List of providers | name | slug, comments, tags, asn, account_num, portal_url ***circuit***
| provider.circuit | List of this providers circuits | cid, type | descr, tags, tenant, commit_rate


### Virtual - *Cluster-group, Cluster-type, Cluster*

Clusters are groupings of resources which VMs run within. Cluster-groups and types allow further grouping of clusters based on things such as location or technology. Site, tenant, cluster-group and tags can be set globally for all members of a cluster-type or be overridden on a per-cluster basis.

| Object   | Description          | Mandatory | Optional |
| -------- | -------------------- | --------- | ---------|
| cluster_group | List of groups (optional) | name | slug, descr, tags
| cluster_type | List of cluster type | name | slug, descr, tags, ***cluster***
| cluster_type.cluster | List of clusters of this cluster type | name | comment, tags, site, tenant, group,

### Contacts - *Contact-role, Contact-group, Contact Assignment*

Contacts are actually created under the organisation menu but are defined separately as they can be assigned to a tenant, site, location, rack, manufacturer, clustergroup, cluster, provider, circuit (possibly also Device, PowerPanel, Region, SiteGroup, and VirtualMachine but not tested)

| Object   | Description          | Mandatory | Optional |
| -------- | -------------------- | --------- | ---------|
| contact_role | List of contact roles  | name | slug, descr, tags
| contact_group | List of contact groups | name | slug, descr, tags
| contact_group.contact | List of contacts (can only be member of 1 group) | name | comments, tags, phone, email, addr
| contact_assign | Assign contacts to roles | assign_to, role, contact | priority

## Installation and Prerequisites

This has been tested against v3.1.7, it wont work on v2.x due to the major changes made to Netbox. Clone the repository and create a virtual environment.

```css
git clone https://github.com/sjhloco/netbox_env_setup.git
python -m venv ~/venv/nbox/
source ~/venv/nbox/bin/activate
```

Install the required packages, it uses *pynetbox 6.4.1* as bug with later versions breaks *nb.ipam.vlans.get()*

```bash
pip install -r requirements.txt
```

The first section of the script holds customisable values for the default base directory and folder name (used if not defined at run time), device-type template directory, SSL cert location (if using HTTPS with a self-signed certificate) and NetBox API URL.

```bash
dvc_type_dir = os.path.join(os.getcwd(), "device_type")
base_dir = os.getcwd()
input_dir = "full_example"

netbox_url = "http://10.30.10.104:8000/"
token = config.api_token
os.environ['REQUESTS_CA_BUNDLE'] = '/Users/user1/Documents/nbox_py_scripts/myCA.pem'
```

The token is set in a separate `config.py` variable file that I *.gitignore* so as not to share the token with the rest of the world. This is imported with `import config` so you either need to add this file or if you want to input the token directly in the script remove the import line. All that *config.py* holds is a single token variable:

```bash
token = 'my_token_got_from_netbox'
```

## Usage

Before running ***nbox_env_setup.py*** it is recommended to use ***input_validate.py*** to verify the contents of input YAML file. It is an offline script (doesn't connect to NetBox) that verifies things such as:

- All parent dictionaries (*tenant, manufacturer, rir, role, crt_type, provider, cluster_type*) are present and the key is a list (can be an empty list if not used)\
- All mandatory dictionaries are present\
- All Dictionary keys that are meant to be a list, integer, boolean or IPv4 address are of the correct format\
- All referenced objects such as tenant, site, rack_role, etc, exist within the input file\
- No duplicate object names

If you are not running all tests (for example don't have organisation defined) you will get dependency warnings as it will look for objects such as sites and tenants which don't exist. Can either ignore or add these to the lists *all_site*, *all_tnt* and *all_obj*.

```bash
python input_validate.py simple_example
```

The script can be run with no flags to create all objects or with flags to only create specific section objects.

| Flag     | Description |
| -------- | ----------- |
| `-o` or `--organisation` | Create Organistaion objects (Circuit-type, Provider, Circuit)
| `-d` or `--device` | Create Device objects (Manufacturers, Platforms, Device-types, Device-roles)
| `-i` or `--ipam` | Create IPAM objects (RIR, Aggregates, Prefix/VLAN roles, VLAN groups, VLANs, VRFs, Prefixes)
| `-p` or `--provider` | Create Provider objects (Circuit-type, Provider, Circuit)
| `-c` or `--contact` | Create Contact objects (Cluster-group, Cluster-type, Cluster)
| `-v` or `--virtual` | Create Virtualisation objects (Contact-role, Contact-group, Contact Assignment)
| none | Create everything

```python
python nbox_env_setup.py simple_example.yml
```

There are three possible outcomes from the attempt to create each object which are relayed back in stdout:\
✅ Object created\
⚠️ Object already exists\
❌ Object can’t be created due to the defined error

![run_example_video](https://user-images.githubusercontent.com/33333983/154144431-9cbf0e5d-24d6-4bc2-b580-5096d29f0047.gif)
