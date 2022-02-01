"""
###### Netbox Base - Setup the base netbox environment ######
Creates the environment within NetBox ready for adding devices, it does not add the devices themselves.
This script is not idempotent. Its purpose to add objects rather than edit or delete existing objects.
The environment is defined in a YAML file that follows the hierarchical structure of NetBox.
The script also follows this structure allowing for subsections of the environment to be created or additions to an already pre-existing environment.

Under the engine you can hash out a section so it only runs the sectiosn you want to create objects for.
-1. ORG_TNT_SITE_RACK: Create all the organisation objects
-2. DVC_MTFR_TYPE: Create all the objects required to create devices
-3. IPAM_VRF_VLAN: Create all the IPAM objects
-4. CRT_PVDR: Create all the Circuit objects
-5. VIRTUAL: Creates all the Cluster objects

It is advisable to run the validation script against the input file to ensure the formatting of the input file is correct
python input_validate.py test.yml
python nbox_env_setup.py simple_example.yml
"""

from pprint import pprint

# import config
from typing import Any, Dict, List
import pynetbox
from pynetbox.core.query import RequestError
import yaml
import operator
import os
import ast
from sys import argv
import os
from rich.console import Console
from rich.theme import Theme
import ipdb
from collections import defaultdict

# ----------------------------------------------------------------------------
# Variables to change dependant on environment
# ----------------------------------------------------------------------------
# Directory that holds all device type templates
dvc_type_dir = os.path.expanduser(
    "~/Documents/Coding/Netbox/nbox_py_scripts/netbox_env_setup/device_type"
)

# # Netbox login details (create from your user profile or in admin for other users)
# netbox_url = "https://10.10.10.101"
# token = config.api_token
# # If using Self-signed cert must have been signed by a CA (can all be done on same box in opnessl) and this points to that CA cert
# os.environ["REQUESTS_CA_BUNDLE"] = os.path.expanduser(
#     "~/Documents/Coding/Netbox/nbox_py_scripts/myCA.pem"
# )

# For docker test environment
token = "0123456789abcdef0123456789abcdef01234567"
netbox_url = "http://10.10.10.104:8000/"
# netbox_url = "http://10.103.40.120:8000/"

# ----------------------------------------------------------------------------
# INZT_LOAD: Opens netbox connection and loads the variable file
# ----------------------------------------------------------------------------
class Nbox:
    def __init__(self, netbox_url: str, token: str):
        self.nb = pynetbox.api(url=netbox_url, token=token)
        my_theme = {"repr.ipv4": "none", "repr.number": "none", "repr.call": "none"}
        self.rc = Console(theme=Theme(my_theme))

    # ----------------------------------------------------------------------------
    # OBJ_CHECK: API call to check if objects already exists in Netbox (e.g. Tenants, tenancy.tenants, tnt, name)
    # ----------------------------------------------------------------------------
    def obj_check(
        self, api_attr: str, obj_fltr: str, obj_dm: Dict[str, Any]
    ) -> Dict[str, Dict]:
        # Creates 2 lists of DMs based on whether the object already exists or not
        obj_notexist_dm, obj_exist_name = ([] for i in range(2))

        for each_obj_dm in obj_dm:
            fltr = {obj_fltr: each_obj_dm[obj_fltr]}
            if operator.attrgetter(api_attr)(self.nb).get(**fltr) == None:
                obj_notexist_dm.append(each_obj_dm)
            else:
                if obj_fltr == "slug":
                    obj_exist_name.append(
                        each_obj_dm["name"] + f" ({each_obj_dm[obj_fltr]})"
                    )
                else:
                    obj_exist_name.append(each_obj_dm[obj_fltr])
        return dict(notexist_dm=obj_notexist_dm, exist_name=obj_exist_name)

    # ----------------------------------------------------------------------------
    # OBJ_CREATE: If not already present adds the object. If for any reason fails returns error message
    # ----------------------------------------------------------------------------
    def obj_create(
        self,
        output_name: str,
        api_attr: str,
        obj_notexist_dm: List,
        obj_exist_name: List,
    ) -> None:
        all_result = []
        if len(obj_notexist_dm) != 0:
            try:
                result = operator.attrgetter(api_attr)(self.nb).create(obj_notexist_dm)
            except RequestError as e:
                # ERR: Message is a string but has the format of list of dicts, literal_eval converts back into a list
                err_msg = ast.literal_eval(e.error)
                for err in err_msg:
                    if len(err) != 0:  # safe guards against empty dicts
                        self.rc.print(
                            f":x: [b]{output_name}[/b] '{list(err.keys())[0]}' - {', '.join(list(err.values())[0])}"
                        )
        # If result variable exists means an object was created
        if "result" in locals():
            all_result = result
        # PRINT: Prints object already exists or create message
        self.result_msg(output_name, obj_exist_name, all_result)

    # ----------------------------------------------------------------------------
    # RESULT_MSG: Reports if device was created or already existed
    # ----------------------------------------------------------------------------
    def result_msg(self, output_name: str, obj_exist_name: List, result: List) -> None:
        # EXISTING: Message returned if already exists (as long as no errors)
        if len(obj_exist_name) != 0:
            self.rc.print(
                f"⚠️  [b]{output_name}[/b]: '{', '.join(obj_exist_name)}' already exist"
            )
        # NEW: Message returned if try/except created a new object
        if len(result) != 0:
            self.rc.print(
                f":white_check_mark: [b]{output_name}[/b]: '{str(result).replace('[', '').replace(']', '')}' successfully created"
            )

    # ----------------------------------------------------------------------------
    # MERGE_DICT: Merges dictionaires for dev_type component error messages
    # ----------------------------------------------------------------------------
    def merge_dict(self, err_msg: List) -> str:
        tmp_err_msg = defaultdict(list)
        error = []
        # Merge all dicts with the same key
        for err in err_msg:
            if len(err) != 0:
                tmp_err_msg[list(err.keys())[0]].append(list(err.values())[0][0])
        # Remove all duplicates in value and turn into a list of string err message
        error = []
        for err_type, err in tmp_err_msg.items():
            tmp_err = set(err)
            error.append(err_type + ": " + ", ".join(tmp_err))
        # return a string of all errors
        return ", ".join(error)

    # ----------------------------------------------------------------------------
    # DEV_TYPE_COMP_CREATE: Adds components of the device_type (intf, power, etc)
    # ----------------------------------------------------------------------------
    def dev_type_comp_create(self, each_type: Dict[str, Any], output_name: str) -> List:
        component = dict(
            interface="interface_templates",
            power="power_port_templates",
            console="console_port_templates",
            rear_port="rear_port_templates",
            front_port="front_port_templates",
        )
        cmpt_created = []
        try:
            for cmpt, api in component.items():
                if len(each_type[cmpt]) != 0:
                    # Creates everything except 'Front-port' as it needs the rear-port ID to map to it (as name is shared)
                    if cmpt != "front_port":
                        operator.attrgetter(api)(self.nb.dcim).create(each_type[cmpt])
                    # front-port needs rear_port ID (using device_type ID) to get the  to map front to rear ports (patch-panels)
                    elif cmpt == "front_port":
                        # breakpoint()
                        dt_id = self.nb.dcim.device_types.get(slug=each_type["slug"]).id
                        for port in each_type[cmpt]:
                            port["rear_port"] = list(
                                self.nb.dcim.rear_port_templates.filter(
                                    name=port["name"], devicetype_id=dt_id
                                )
                            )[0].id
                        operator.attrgetter(api)(self.nb.dcim).create(each_type[cmpt])
                cmpt_created.append(cmpt)
            return cmpt_created
        # DEV_TYPE_COMP_ERR: If dev_type component was not able to be created returns an error message
        except RequestError as e:
            err_msg = ast.literal_eval(e.error)
            error = self.merge_dict(err_msg)
            dev_model = each_type["model"]
            self.rc.print(
                f":x: [b]{output_name}[/b]: Failed to create '{dev_model}' because of errors with '{cmpt}' component - {error}"
            )
            return []

    # ----------------------------------------------------------------------------
    # DEV_TYPE_CREATE: If not already present and no componets fail adds the device_type
    # ----------------------------------------------------------------------------
    def dev_type_create(
        self,
        output_name: str,
        api_attr: str,
        obj_notexist_dm: List,
        obj_exist_name: List,
    ) -> None:
        all_result = []
        if len(obj_notexist_dm) != 0:
            for each_type in obj_notexist_dm:
                # DEV_TYPE: Tries to create the device_type, if fails returns error message
                try:
                    result = operator.attrgetter(api_attr)(self.nb).create(each_type)
                    # DEV_TYPE_COMP: If dev_type creation succeeds tries to create each device_type component
                    comp_created = self.dev_type_comp_create(each_type, result)
                    # Dependant on component result either adds dev_type to result message or deletes
                    if len(comp_created) != 0:
                        all_result.append(
                            result
                        )  # add dev_type name to print success message
                    elif len(comp_created) == 0:
                        self.nb.dcim.device_types.get(model=each_type["model"]).delete()
                # DEV_TYPE_ERR: If dev_type was not able to be created returns an error message
                except RequestError as e:
                    # Converts string error message back into a list (literal_eval)
                    err_msg = ast.literal_eval(e.error)
                    for err in err_msg:
                        if len(err) != 0:
                            self.rc.print(
                                f":x: [b]{output_name}[/b]: {list(err.keys())[0]} - {list(err.values())[0]}"
                            )
        # PRINT: Prints object already exists or create message
        self.result_msg(output_name, obj_exist_name, all_result)

    # ----------------------------------------------------------------------------
    # VLAN/PFX ENGINE: Checks VL_GRP and VRF exist and gets ID used to create VLAN or prefix
    # ----------------------------------------------------------------------------
    def vlan_pfx_engine(
        self, output_name: str, api_attr: str, obj_fltr: str, obj_dm: Dict[str, Any]
    ) -> Dict[str, Any]:
        obj_notexist_dm, obj_exist_name = ([] for i in range(2))
        # VL_GRP/VRF EXIST: Checks if VLAN_GRP or VRF exists, if so gets the id
        for each_obj_dm in obj_dm:
            obj_name = each_obj_dm[obj_fltr[1].split("_")[0]]["name"]
            if operator.attrgetter(api_attr[1])(self.nb).get(name=obj_name) != None:
                obj_id = operator.attrgetter(api_attr[1])(self.nb).get(name=obj_name).id
                # VLAN/PFX EXIST: Uses ID to check if VLAN or PFX already exists in VL_GRP or PFX in the VRF
                fltr = {
                    obj_fltr[0]: each_obj_dm[obj_fltr[0]],
                    obj_fltr[1]: obj_id,
                }
                # If the VLAN or PFX does not exist adds dict to non-exist list, if does adds name to exist list
                if list(operator.attrgetter(api_attr[0])(self.nb).filter(**fltr)) == []:
                    obj_notexist_dm.append(each_obj_dm)
                else:
                    obj_exist_name.append(each_obj_dm[obj_fltr[0]])
            # ERROR: If VRF or VL_GRP dont exist prints message (cant create VLAN/PFX without them)
            elif operator.attrgetter(api_attr[1])(self.nb).get(name=obj_name) == None:
                api_name = api_attr[1].split(".")[1][:-1]
                obj_type = each_obj_dm[obj_fltr[0]]
                self.rc.print(
                    f":x: [b]{output_name}[/b]: {obj_type} - The {api_name} '{obj_name}' for this {output_name.lower()} does not exist"
                )
        # PREFIX_VLAN: If is a Prefix associated to a VLAN checks against VL_GRP and role to get the unique ID
        if api_attr[0] == "ipam.prefixes":
            for each_obj_dm in reversed(obj_notexist_dm):
                # GET_VLAN_ID: If vl_grp exists gets the VLAN ID and add it to the dict
                if each_obj_dm.get("vlan") != None:
                    vlan = each_obj_dm["vlan"]
                    vl_grp = each_obj_dm["vl_grp"]["name"]
                    # Need to first get the slug as needed for group filter in next 2 cmds
                    vl_grp_slug = self.nb.ipam.vlan_groups.get(name=vl_grp)["slug"]
                    if self.nb.ipam.vlans.get(vid=vlan, group=vl_grp_slug) != None:

                        each_obj_dm["vlan"] = dict(
                            id=self.nb.ipam.vlans.get(vid=vlan, group=vl_grp_slug).id
                        )
                    # VLAN_NOT_EXIST: If the vlan does not exists prints an error and removes the prefix
                    else:
                        obj_notexist_dm.remove(each_obj_dm)
                        pfx = each_obj_dm["prefix"]
                        self.rc.print(
                            f":x: [b]{output_name}[/b]: {pfx} - VLAN '{vlan}' in VLAN Group '{vl_grp}' does not exist"
                        )
        # Creates the VLANs and Prefixes
        self.obj_create(output_name, api_attr[0], obj_notexist_dm, obj_exist_name)

    # NBOX_ENGINE: Checks existence of objects and creates them if they do not exist
    def engine(
        self, output_name: str, api_attr: str, obj_fltr: str, obj_dm: Dict[str, Any]
    ) -> None:
        # Check object exists
        obj = self.obj_check(api_attr, obj_fltr, obj_dm)
        # Create objects
        if output_name == "Device-type":
            self.dev_type_create(
                output_name, api_attr, obj["notexist_dm"], obj["exist_name"]
            )
        else:
            self.obj_create(
                output_name, api_attr, obj["notexist_dm"], obj["exist_name"]
            )

    # TAGS: Gathers ID of existing tag or creates new one and returns ID (list of IDs)
    def get_or_create_tag(self, tag: Dict[str, Any]) -> List:
        tags = []
        if tag != None:
            for name, colour in tag.items():
                name = str(name)
                tag = self.nb.extras.tags.get(name=name)
                if not tag:
                    tag = self.nb.extras.tags.create(
                        dict(name=name, slug=self.make_slug(name), color=colour)
                    )
                    tag_created.append(name)
                else:
                    tag_exists.append(name)
                tags.append(tag.id)
        return tags

    # RT: Gathers ID of existing RT or creates new one and returns ID (list of IDs)
    def get_or_create_rt(self, rt: List, tnt: str) -> List:
        all_rt = []
        if isinstance(rt, list):
            rt = dict.fromkeys(rt, "")
        if rt != None:
            for name, descr in rt.items():
                rt = self.nb.ipam.route_targets.get(name=name)
                if not rt:
                    fltr = {"name": name, "description": descr, "tenant": {"name": tnt}}
                    rt = self.nb.ipam.route_targets.create(**fltr)
                    rt_created.append(name)
                else:
                    rt_exists.append(name)

                all_rt.append(rt.id)
        return all_rt

    # PRINT_TAG_RT: Prints the result of existing and newly created tags
    def print_tag_rt(self, input_msg, exists, created) -> None:
        if len(created) != 0:
            self.rc.print(
                f":white_check_mark: [b]{input_msg}[/b]: '{', '.join(created)}' successfully created"
            )
        elif len(exists) != 0:
            self.rc.print(
                f"⚠️  [b]{input_msg}[/b]: '{', '.join(exists)}' already exist"
            )

    # SLUG: If slug is empty replaces it with tenant name (lowercase) replacing whitespace with '_'
    def make_slug(self, obj: str) -> str:
        if isinstance(obj, int):
            obj = str(obj)
        return obj.replace(" ", "_").lower()

    # TNT: Gets the tennat name for a a site fed into it (if API call fails leaves blank)
    def get_tnt(self, site: Dict[str, Any]) -> str:
        try:
            return dict(self.nb.dcim.sites.get(name=site))["tenant"]["name"]
        except:
            return None


# ----------------------------------------------------------------------------
# 1. ORG_TNT_SITE_RACK: Creates the DM for organisation objects tenant, site, rack-group and rack
# ----------------------------------------------------------------------------
class Organisation(Nbox):
    def __init__(self, tenant: List, rack_role: List) -> None:
        super().__init__(netbox_url, token)
        self.tenant = tenant
        self.rack_role = rack_role
        self.tnt, self.site, self.loc = ([] for i in range(3))
        self.rack, self.rr = ([] for i in range(2))

    # 1a. TNT: Create Tenant dictionary
    def cr_tnt(self, each_tnt: Dict[str, Any]) -> Dict[str, Any]:
        return dict(
            name=each_tnt["name"],
            slug=each_tnt.get("slug", self.make_slug(each_tnt["name"])),
            description=each_tnt.get("descr", ""),
            tags=self.get_or_create_tag(each_tnt.get("tags")),
        )

    # 1b. SITE: Uses temp dict and joins as the ASN cant be None, it must be an integer.
    def cr_site(
        self, each_tnt: Dict[str, Any], each_site: Dict[str, Any]
    ) -> Dict[str, Any]:
        temp_site = dict(
            name=each_site["name"],
            slug=each_site.get("slug", self.make_slug(each_site["name"])),
            # tenant is a nested dict as uses name rather than id
            tenant=dict(name=each_tnt["name"]),
            time_zone=each_site.get("time_zone", "UTC"),
            description=each_site.get("descr", ""),
            physical_address=each_site.get("addr", ""),
            contact_name=each_site.get("contact", ""),
            contact_phone=each_site.get("phone", ""),
            contact_email=each_site.get("email", ""),
            tags=self.get_or_create_tag(each_site.get("tags")),
        )
        if each_site.get("ASN") != None:
            temp_site["asn"] = each_site["ASN"]
        return temp_site

    # 1c. LOCATION: Method run to create parent and child location
    def cr_loc_rack(
        self,
        each_loc: Dict[str, Any],
        each_site: Dict[str, Any],
        each_tnt: Dict[str, Any],
        parent: str,
    ) -> Dict[str, Any]:

        tmp_loc = dict(
            name=each_loc["name"],
            slug=each_loc.get("slug", self.make_slug(each_loc["name"])),
            site=dict(name=each_site["name"]),
            description=each_loc.get("descr", ""),
        )
        if parent != None:
            tmp_loc["parent"] = dict(name=parent)
        self.loc.append(tmp_loc)

        # 1d. RACK: Creates list of racks within the location
        if each_loc.get("rack") != None:
            for each_rack in each_loc["rack"]:
                temp_rack = dict(
                    name=each_rack["name"],
                    # Site and group are dict as using dictionary of attributes rather than ID
                    site=dict(name=each_site["name"]),
                    location=dict(
                        slug=each_loc.get("slug", self.make_slug(each_loc["name"]))
                    ),
                    tenant=dict(name=each_rack.get("tenant", each_tnt["name"])),
                    u_height=each_rack.get("height", 42),
                    tags=self.get_or_create_tag(each_rack.get("tags")),
                )
                # Needed as Role cant be blank
                if each_rack.get("role") != None:
                    temp_rack["role"] = dict(name=each_rack["role"])
                self.rack.append(temp_rack)
        # Only returned for unittesting
        return tmp_loc, self.rack

    # 1e. RR: Rack roles that can be used by a rack. If undefined sets the colour to white as cant be empty
    def cr_rr(self, each_rr: Dict[str, Any]) -> Dict[str, Any]:
        return dict(
            name=each_rr["name"],
            slug=each_rr.get("slug", self.make_slug(each_rr["name"])),
            description=each_rr.get("descr", ""),
            color=each_rr.get("color", "ffffff"),
        )

    # ENGINE: Runs all the other methods in this class to create dict used to create nbox objects
    def create_tnt_site_rack(self) -> Dict[str, Any]:
        # 1a. TNT: Create Tenant dictionary
        for each_tnt in self.tenant:
            self.tnt.append(self.cr_tnt(each_tnt))
            # 1b. SITE: Create site dictionary
            for each_site in each_tnt.get("site", []):
                self.site.append(self.cr_site(each_tnt, each_site))
                # 1c. LOC_RACK: Creates list of locations and racks at the site
                if each_site.get("location") != None:
                    for each_loc in each_site["location"]:
                        self.cr_loc_rack(each_loc, each_site, each_tnt, None)
                        # 1d. NESTED_LOC_RACK: List of nested locations and racks within them
                        if each_loc.get("location") != None:
                            for each_child_loc in each_loc["location"]:
                                self.cr_loc_rack(
                                    each_child_loc,
                                    each_site,
                                    each_tnt,
                                    each_loc["name"],
                                )
        # 1e. RR: Creates the Rack roles dictionary that can be used by a rack.
        for each_rr in self.rack_role:
            self.rr.append(self.cr_rr(each_rr))
        # The Data Models returned to the main method that are used to create the object
        return dict(
            tnt=self.tnt,
            site=self.site,
            location=self.loc,
            rack=self.rack,
            rack_role=self.rr,
        )


# ----------------------------------------------------------------------------
# 2. DVC_MFTR_TYPE: Creates the DM for device objects manufacturer, platform, dvc_role and dvc_type
# ----------------------------------------------------------------------------
class Devices(Nbox):
    def __init__(self, device_role: List, manufacturer: List) -> None:
        super().__init__(netbox_url, token)
        self.device_role = device_role
        self.manufacturer = manufacturer
        self.dev_role, self.mftr, self.pltm, self.dev_type = ([] for i in range(4))

    # 2a. DEV_ROLE: List of device roles for all sites
    def cr_dev_role(self, each_role: Dict[str, Any]) -> Dict[str, Any]:
        return dict(
            name=each_role["name"],
            slug=each_role.get("slug", self.make_slug(each_role["name"])),
            color=each_role.get("color", "ffffff"),
            description=each_role.get("descr", ""),
            vm_role=each_role.get("vm_role", True),
        )

    # 2b. MFTR: List of manufacturers for all sites
    def cr_mftr(self, each_mftr: Dict[str, Any]) -> Dict[str, Any]:
        return dict(
            name=each_mftr["name"],
            slug=each_mftr.get("slug", self.make_slug(each_mftr["name"])),
            description=each_mftr.get("descr", ""),
        )

    # 2c. PLATFORM: List of platforms for the manufacturer. Uses 'if' as platform is optional
    def cr_pltm(self, mftr: str, each_pltm: Dict[str, Any]) -> Dict[str, Any]:
        return dict(
            name=each_pltm["name"],
            slug=each_pltm.get("slug", self.make_slug(each_pltm["name"])),
            manufacturer=dict(name=mftr),
            description=each_pltm.get("descr", ""),
            napalm_driver=each_pltm.get("driver", self.make_slug(each_pltm["name"])),
        )

    # DEV_TYPE_CONN: Creates each device type connection object
    def cr_conn(
        self, model: str, conn_name: str, conn_type: str, intf_mgmt=None
    ) -> Dict[str, Any]:
        dev_type_obj = dict(
            device_type=dict(model=model), name=conn_name, type=conn_type
        )
        if intf_mgmt != None:
            dev_type_obj.update(dict(mgmt_only=intf_mgmt))
        return dev_type_obj

    # 2d. DVC_TYPE: List of device types for the manufacturer. Uses 'if' as device_type is optional
    def cr_dev_type(self, mftr: str, each_type: Dict[str, Any]) -> Dict[str, Any]:
        # Lists need to be emptied each loop (dev_type)
        intf, con, pwr, f_port, r_port = ([] for i in range(5))
        with open(os.path.join(dvc_type_dir, each_type), "r") as file_content:
            dev_type_tmpl = yaml.load(file_content, Loader=yaml.FullLoader)

        # Create lists of interfaces, consoles, power, front_ports and rear_ports
        for each_intf in dev_type_tmpl.get("interfaces", []):
            intf.append(
                self.cr_conn(
                    dev_type_tmpl["model"],
                    each_intf["name"],
                    each_intf["type"],
                    each_intf.get("mgmt_only", False),
                )
            )
        for each_con in dev_type_tmpl.get("console-ports", []):
            con.append(
                self.cr_conn(dev_type_tmpl["model"], each_con["name"], each_con["type"])
            )
        for each_pwr in dev_type_tmpl.get("power-ports", []):
            pwr.append(
                self.cr_conn(dev_type_tmpl["model"], each_pwr["name"], each_pwr["type"])
            )
        for each_fport in dev_type_tmpl.get("front_port", []):
            # Creates the list of front and rear ports from a start and end port number (of front port)
            for each_port in range(
                each_fport["start_port"], each_fport["end_port"] + 1
            ):
                r_port.append(
                    self.cr_conn(dev_type_tmpl["model"], each_port, each_fport["type"])
                )
                f_port.append(
                    self.cr_conn(dev_type_tmpl["model"], each_port, each_fport["type"])
                )
        # Create list of device types which also includes the interfaces, consoles, power, front_port and rear_port lists
        return dict(
            manufacturer=dict(name=mftr),
            model=dev_type_tmpl["model"],
            slug=dev_type_tmpl["slug"],
            part_number=dev_type_tmpl["part_number"],
            u_height=dev_type_tmpl.get("u_height", 1),
            is_full_depth=dev_type_tmpl.get("is_full_depth", True),
            interface=intf,
            console=con,
            power=pwr,
            front_port=f_port,
            rear_port=r_port,
        )

    # ENGINE: Runs all the other methods in this class to create dict used to create nbox objects
    def create_dvc_type_role(self) -> Dict[str, Any]:
        # 2a. DEV_ROLE: Create Device Role dictionary
        for each_role in self.device_role:
            self.dev_role.append(self.cr_dev_role(each_role))
        # 2b. MFTR: Create Manufacturer dictionary
        for each_mftr in self.manufacturer:
            self.mftr.append(self.cr_mftr(each_mftr))
            # 2c. PLATFORM: Create Platform dictionary
            if each_mftr.get("platform") != None:
                for each_pltm in each_mftr["platform"]:
                    self.pltm.append(self.cr_pltm(each_mftr["name"], each_pltm))
            # 2d. DEV_TYPE: Create Device Type dictionary
            if each_mftr.get("device_type") != None:
                for each_type in each_mftr["device_type"]:
                    self.dev_type.append(self.cr_dev_type(each_mftr["name"], each_type))

        # 2e. The Data Models returned to the main method that are used to create the objects
        return dict(
            dev_role=self.dev_role,
            mftr=self.mftr,
            pltm=self.pltm,
            dev_type=self.dev_type,
        )


# ----------------------------------------------------------------------------
# 3. IPAM_VRF_VLAN: Creates the DM for IPAM objects RIR, aggregate, VRF and VLAN
# ----------------------------------------------------------------------------
class Ipam(Nbox):
    def __init__(self, rir: List, role: List) -> None:
        super().__init__(netbox_url, token)
        self.ipam_rir = rir
        self.pfx_vlan_role = role
        self.rir, self.aggr, self.role, self.vlan_grp = ([] for i in range(4))
        self.vlan, self.vrf, self.pfx = ([] for i in range(3))

    # 3a. RIR: If slug is empty replaces it with tenant name (lowercase) replacing whitespace with '_'
    def cr_rir(self, each_rir: Dict[str, Any]) -> Dict[str, Any]:
        return dict(
            name=each_rir["name"],
            slug=each_rir.get("slug", self.make_slug(each_rir["name"])),
            description=each_rir.get("descr", ""),
            is_private=each_rir.get("is_private", False),
        )

    # 3b. AGGREGATE: Create ranges that are associated to the RIR
    def cr_aggr(
        self, each_rir: Dict[str, Any], each_aggr: Dict[str, Any]
    ) -> Dict[str, Any]:
        return dict(
            rir=dict(name=each_rir["name"]),
            prefix=each_aggr["prefix"],
            description=each_aggr.get("descr", ""),
            tags=self.get_or_create_tag(each_aggr.get("tags")),
        )

    # 3c. ROLE: Provides segregation of networks (i.e prod, npe, etc), applies to all VLANs and prefixes beneath it
    def cr_role(self, each_role: Dict[str, Any]) -> Dict[str, Any]:
        return dict(
            name=each_role["name"],
            slug=each_role.get("slug", self.make_slug(each_role["name"])),
            description=each_role.get("descr", ""),
        )

    # 3d. VL_GRP: Creates per site VLAN group that holds VLANs that are unique to that group
    def cr_vl_grp(self, site: str, each_vlgrp: Dict[str, Any]) -> Dict[str, Any]:
        return dict(
            name=each_vlgrp["name"],
            slug=each_vlgrp.get("slug", self.make_slug(each_vlgrp["name"])),
            site=dict(name=site),
            description=each_vlgrp.get("descr", ""),
        )

    # 3e. VLAN: Creates VLANs and associate to the vl_grp, tenant, site and role. The VL_GRP and role keep them unique
    def cr_vlan(
        self,
        role: str,
        vl_grp_tnt: str,
        each_vlgrp: Dict[str, Any],
        each_vl: Dict[str, Any],
    ) -> Dict[str, Any]:
        return dict(
            vid=each_vl["id"],
            name=each_vl["name"],
            role=dict(name=role),
            tenant=dict(name=each_vl.get("tenant", vl_grp_tnt)),
            group=dict(name=each_vlgrp["name"]),
            description=each_vl.get("descr", ""),
            tags=self.get_or_create_tag(each_vl.get("tags")),
        )

    # 3f. VRF: If defined in the VLAN Group creates VRF
    def cr_vrf(self, vrf_tnt: str, each_vrf: Dict[str, Any]) -> Dict[str, Any]:
        tmp_vrf = dict(
            name=each_vrf["name"],
            description=each_vrf.get("descr", ""),
            enforce_unique=each_vrf.get("unique", True),
            tenant=dict(name=vrf_tnt),
            tags=self.get_or_create_tag(each_vrf.get("tags")),
            import_targets=self.get_or_create_rt(
                each_vrf.get("import_rt"),
                vrf_tnt,
            ),
            export_targets=self.get_or_create_rt(
                each_vrf.get("export_rt"),
                vrf_tnt,
            ),
        )
        if each_vrf.get("rd") != None:
            tmp_vrf["rd"] = each_vrf["rd"]
        return tmp_vrf

    # 3g. PREFIX: Associated to a VRF, role and possibly a VLANs (SVIs) within the VLAN group. VRF and role are what make the prefix unique
    def cr_pfx(
        self,
        role: str,
        site: str,
        vrf_tnt: str,
        vlgrp: str,
        vrf: str,
        each_pfx: Dict[str, Any],
    ) -> Dict[str, Any]:
        tmp_pfx = dict(
            prefix=each_pfx["pfx"],
            role=dict(name=role),
            is_pool=each_pfx.get("pool", True),
            vrf=dict(name=vrf),
            description=each_pfx.get("descr", ""),
            site=dict(name=site),
            tenant=dict(name=each_pfx.get("tenant", vrf_tnt)),
            tags=self.get_or_create_tag(each_pfx.get("tags")),
        )
        if vlgrp != None:
            tmp_pfx["vl_grp"] = dict(name=vlgrp)
        if each_pfx.get("vl") != None:
            tmp_pfx["vlan"] = each_pfx["vl"]
        return tmp_pfx

    # ENGINE: Runs all the other methods in this class to create dict used to create nbox objects
    def create_ipam(self) -> Dict[str, Any]:
        # 3a. RIR: Create RIR dictionary
        for each_rir in self.ipam_rir:
            self.rir.append(self.cr_rir(each_rir))
            # 3b. AGGR: Create Aggregate dictionary
            if each_rir.get("ranges") != None:
                for each_aggr in each_rir["ranges"]:
                    self.aggr.append(self.cr_aggr(each_rir, each_aggr))
        # 3c. ROLE: Create Role dictionary
        for each_role in self.pfx_vlan_role:
            self.role.append(self.cr_role(each_role))
            # Loops through sites to create vlans and prefixes
            for each_site in each_role["site"]:
                tnt = self.get_tnt(each_site["name"])
                # 3d. VL_GRP: Creates per-site VLAN Group Dictionary
                if each_site.get("vlan_grp") != None:
                    for each_vlgrp in each_site["vlan_grp"]:
                        vl_grp_tnt = each_vlgrp.get("tenant", tnt)
                        self.vlan_grp.append(
                            self.cr_vl_grp(each_site["name"], each_vlgrp)
                        )
                        # 3e. VLAN: Creates per-vlan-group VLAN Dictionary
                        for each_vl in each_vlgrp["vlan"]:
                            self.vlan.append(
                                self.cr_vlan(
                                    each_role["name"],
                                    vl_grp_tnt,
                                    each_vlgrp,
                                    each_vl,
                                )
                            )
                        # 3f. VRF: Creates per-vlan-group VRF Dictionary
                        if each_vlgrp.get("vrf") != None:
                            for each_vrf in each_vlgrp["vrf"]:
                                vrf_tnt = each_vrf.get("tenant", tnt)
                                self.vrf.append(self.cr_vrf(vrf_tnt, each_vrf))
                                # 3g. PREFIX: Creates per-vrf Prefix Dictionary
                                for each_pfx in each_vrf["prefix"]:
                                    self.pfx.append(
                                        self.cr_pfx(
                                            each_role["name"],
                                            each_site["name"],
                                            vrf_tnt,
                                            each_vlgrp["name"],
                                            each_vrf["name"],
                                            each_pfx,
                                        )
                                    )
                # 3h. VRF_WITH_NO_VLANs: If Prefixes do not have VLANs no VL_GRP, the VRF is the main dictionary with PFX dictionaries underneath it
                if each_site.get("vrf") != None:
                    # VRF: Creates VRF withs its optional settings
                    for each_vrf in each_site["vrf"]:
                        vrf_tnt = each_vrf.get("tenant", tnt)
                        self.vrf.append(self.cr_vrf(vrf_tnt, each_vrf))
                        # 3i. PREFIX: Creates per-vrf Prefix Dictionary
                        for each_pfx in each_vrf["prefix"]:
                            self.pfx.append(
                                self.cr_pfx(
                                    each_role["name"],
                                    each_site["name"],
                                    vrf_tnt,
                                    None,
                                    each_vrf["name"],
                                    each_pfx,
                                )
                            )
        # 3j. The Data Models returned to the main method that are used to create the objects
        return dict(
            rir=self.rir,
            aggr=self.aggr,
            role=self.role,
            vlan_grp=self.vlan_grp,
            vlan=self.vlan,
            vrf=self.vrf,
            prefix=self.pfx,
        )


# ----------------------------------------------------------------------------
# 4. CRT_PVDR: Creates the DM for Circuit, Provider and Circuit Type
# ----------------------------------------------------------------------------
class Circuits(Nbox):
    def __init__(self, circuit_type: List, provider: List) -> None:
        super().__init__(netbox_url, token)
        self.circuit_type = circuit_type
        self.provider = provider
        self.crt_type, self.pvdr, self.crt = ([] for i in range(3))

    # 4a. CIRCUIT_TYPE: A classification of circuits
    def cr_crt_type(self, each_type: Dict[str, Any]) -> Dict[str, Any]:
        return dict(
            name=each_type["name"],
            slug=each_type.get("slug", self.make_slug(each_type["name"])),
            description=each_type.get("descr", ""),
        )

    # 4b. PROVIDER: Containers that hold cicuits by the same provider of connectivity (ISP)
    def cr_pvdr(self, each_pvdr: Dict[str, Any]) -> Dict[str, Any]:
        tmp_pvdr = dict(
            name=each_pvdr["name"],
            slug=each_pvdr.get("slug", self.make_slug(each_pvdr["name"])),
            account=each_pvdr.get("account_num", ""),
            portal_url=each_pvdr.get("portal_url", ""),
            noc_contact=each_pvdr.get("noc_contact", ""),
            admin_contact=each_pvdr.get("admin_contact", ""),
            comments=each_pvdr.get("comments", ""),
            tags=self.get_or_create_tag(each_pvdr.get("tags")),
        )
        # Optional setting ASN
        if each_pvdr.get("asn") != None:
            tmp_pvdr["asn"] = each_pvdr["asn"]
        return tmp_pvdr

    # 4c. CIRCUIT: Each circuit belongs to a provider and must be assigned a circuit ID which is unique to that provider
    def cr_crt(
        self, each_pvdr: Dict[str, Any], each_crt: Dict[str, Any]
    ) -> Dict[str, Any]:
        tmp_crt = dict(
            cid=str(each_crt["cid"]),
            type=dict(name=each_crt["type"]),
            provider=dict(name=each_pvdr["name"]),
            description=each_crt.get("descr", ""),
            tags=self.get_or_create_tag(each_crt.get("tags")),
        )
        # Optional settings Tenant and commit_rate need to be only added if set as empty vlaues breal API calls
        if each_crt.get("tenant") != None:
            tmp_crt["tenant"] = dict(name=each_crt["tenant"])
        if each_crt.get("commit_rate") != None:
            tmp_crt["commit_rate"] = each_crt["commit_rate"]
        return tmp_crt

    # ENGINE: Runs all the other methods in this class to create dict used to create nbox objects
    def create_crt_pvdr(self) -> Dict[str, Any]:
        # 4a. CRT_TYPE: Create Circuit Type dictionary
        for each_type in self.circuit_type:
            self.crt_type.append(self.cr_crt_type(each_type))
        # 4b. PVDR: Create Provider dictionary
        for each_pvdr in self.provider:
            self.pvdr.append(self.cr_pvdr(each_pvdr))
            # 4c. CRT: Create Circuit dictionary
            for each_crt in each_pvdr["circuit"]:
                self.crt.append(self.cr_crt(each_pvdr, each_crt))
        # 4c. The Data Models returned to the main method that are used to create the objects
        return dict(crt_type=self.crt_type, pvdr=self.pvdr, crt=self.crt)


# ----------------------------------------------------------------------------
# 5. VIRTUAL: Creates the DM for Cluster, cluster type and cluster group
# ----------------------------------------------------------------------------
class Virtualisation(Nbox):
    def __init__(self, cluster_group: List, cluster_type: List) -> None:
        super().__init__(netbox_url, token)
        self.cluster_group = cluster_group
        self.cluster_type = cluster_type
        self.cltr_type, self.cltr, self.cltr_grp = ([] for i in range(3))

    # 5a. CLUSTER_GROUP: Optional, can be used to group clusters such as by region. Only required if used in clusters
    def cr_cltr_grp(self, each_grp: Dict[str, Any]) -> Dict[str, Any]:
        return dict(
            name=each_grp["name"],
            slug=each_grp.get("slug", self.make_slug(each_grp["name"])),
            description=each_grp.get("descr", ""),
        )

    # 5b. CLUSTER_TYPE: Represents a technology or mechanism by which to group clusters
    def cr_cltr_type(self, each_type: Dict[str, Any]) -> Dict[str, Any]:
        return dict(
            name=each_type["name"],
            slug=each_type.get("slug", self.make_slug(each_type["name"])),
            description=each_type.get("descr", ""),
        )

    # 5c. CLUSTERS: Holds VMs and physical resources which hosts VMs
    def cr_cltr(
        self, each_type: Dict[str, Any], each_cltr: Dict[str, Any]
    ) -> Dict[str, Any]:
        tmp_cltr = dict(
            name=each_cltr["name"],
            type=dict(name=each_type["name"]),
            comments=each_cltr.get("comment", ""),
        )
        # Optional settings (tenant, site or group), these can be set in cluster or inherited from cluster group
        type_site = each_type.get("site", None)
        if each_cltr.get("site", type_site) != None:
            tmp_cltr["site"] = dict(name=each_cltr.get("site", type_site))
        type_grp = each_type.get("group", None)
        if each_cltr.get("group", type_grp) != None:
            tmp_cltr["group"] = dict(name=each_cltr.get("group", type_grp))
        type_tags = each_type.get("tags", None)
        if each_cltr.get("tags", type_tags) != None:
            tmp_cltr["tags"] = self.get_or_create_tag(each_cltr.get("tags", type_tags))
        # If tenant is undefined in cltr and cltr_grp gets the tenant name from the site (leaves blank if API call fails)
        if each_type.get("tenant") != None:
            type_tnt = each_type.get("tenant", None)
        elif each_type.get("tenant") == None:
            try:
                site = each_cltr.get("site", type_site)
                type_tnt = dict(self.nb.dcim.sites.get(name=site))["tenant"]["name"]
            except:
                type_tnt = None
        if each_cltr.get("tenant", type_tnt) != None:
            tmp_cltr["tenant"] = dict(name=each_cltr.get("tenant", type_tnt))
        return tmp_cltr

    # ENGINE: Runs all the other methods in this class to create dict used to create nbox objects
    def create_vrtl(self) -> Dict[str, Any]:
        # 5a. CLTR_GRP: Create Cluster Group dictionary
        if self.cluster_group != None:
            for each_grp in self.cluster_group:
                self.cltr_grp.append(self.cr_cltr_grp(each_grp))
        # 5b. CLTR_TYPE: Create Cluster Type dictionary
        for each_type in self.cluster_type:
            self.cltr_type.append(self.cr_cltr_grp(each_type))
            # 5c. CLTR_TYPE: Create Cluster Type dictionary
            if each_type.get("cluster") != None:
                for each_cltr in each_type["cluster"]:
                    self.cltr.append(self.cr_cltr(each_type, each_cltr))
        # 5d. The Data Models returned to the main method that are used to create the objects
        return dict(cltr_type=self.cltr_type, cltr=self.cltr, cltr_grp=self.cltr_grp)


######################## ENGINE: Runs the methods of the script ########################
# Used by all object creations so have to be created outside of classes and outside main() or is missing for pytest
global tag_exists, tag_created, rt_exists, rt_created
tag_exists, tag_created, rt_exists, rt_created = ([] for i in range(4))


def main():
    # Opens netbox connection and loads the variable file
    script, first = argv
    with open(argv[1], "r") as file_content:
        my_vars = yaml.load(file_content, Loader=yaml.FullLoader)

    nbox = Nbox(netbox_url, token)

    # 1. ORG_TNT_SITE_RACK: Create all the organisation objects
    # org = Organisation(my_vars["tenant"], my_vars["rack_role"])
    # org_dict = org.create_tnt_site_rack()
    # # Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
    # nbox.engine("Rack Role", "dcim.rack_roles", "name", org_dict["rack_role"])
    # nbox.engine("Tenant", "tenancy.tenants", "name", org_dict["tnt"])
    # nbox.engine("Site", "dcim.sites", "name", org_dict["site"])
    # nbox.engine("Location", "dcim.locations", "slug", org_dict["location"])
    # nbox.engine("Rack", "dcim.racks", "name", org_dict["rack"])

    # # 2. DVC_MTFR_TYPE: Create all the objects required to create devices
    # dvc = Devices(my_vars["device_role"], my_vars["manufacturer"])
    # dvc_dict = dvc.create_dvc_type_role()
    # # Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
    # nbox.engine("Device-role", "dcim.device_roles", "name", dvc_dict["dev_role"])
    # nbox.engine("Manufacturer", "dcim.manufacturers", "name", dvc_dict["mftr"])
    # nbox.engine("Platform", "dcim.platforms", "name", dvc_dict["pltm"])
    # nbox.engine("Device-type", "dcim.device_types", "model", dvc_dict["dev_type"])

    # 3. IPAM_VRF_VLAN: Create all the IPAM objects
    ipam = Ipam(my_vars["rir"], my_vars["role"])
    ipam_dict = ipam.create_ipam()

    # Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
    # nbox.engine("RIRs", "ipam.rirs", "name", ipam_dict["rir"])
    # nbox.engine("Aggregates", "ipam.aggregates", "prefix", ipam_dict["aggr"])
    # nbox.engine("Prefix/VLAN Role", "ipam.roles", "name", ipam_dict["role"])
    # nbox.engine("VLAN Group", "ipam.vlan-groups", "name", ipam_dict["vlan_grp"])
    nbox.engine("VRF", "ipam.vrfs", "name", ipam_dict["vrf"])
    nbox.print_tag_rt("Route-Targets", set(rt_exists), rt_created)

    # First check if VL/PFX exist in VL_GRP/VRF, then if exist in ROLE.
    # nbox.vlan_pfx_engine(
    #     "VLAN",
    #     ["ipam.vlans", "ipam.vlan_groups"],
    #     ["name", "group_id"],
    #     ipam_dict["vlan"],
    # )
    # nbox.vlan_pfx_engine(
    #     "Prefix",
    #     ["ipam.prefixes", "ipam.vrfs"],
    #     ["prefix", "vrf_name"],
    #     ipam_dict["prefix"],
    # )

    # # 4. CRT_PVDR: Create all the Circuit objects
    crt = Circuits(my_vars["circuit_type"], my_vars["provider"])
    crt_dict = crt.create_crt_pvdr()
    # # Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
    # nbox.engine("Circuit Type", "circuits.circuit-types", "name", crt_dict["crt_type"])
    # nbox.engine("Provider", "circuits.providers", "name", crt_dict["pvdr"])
    nbox.engine("Circuit", "circuits.circuits", "cid", crt_dict["crt"])

    # # 5. VIRTUAL: Creates all the Cluster objects
    # vrtl = Virtualisation(my_vars["cluster_group"], my_vars["cluster_type"])
    # vrtl_dict = vrtl.create_vrtl()
    # # Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
    # nbox.engine(
    #     "Cluster Type", "virtualization.cluster-types", "name", vrtl_dict["cltr_type"]
    # )
    # nbox.engine(
    #     "Cluster Group", "virtualization.cluster-groups", "name", vrtl_dict["cltr_grp"]
    # )
    # nbox.engine("Cluster", "virtualization.clusters", "name", vrtl_dict["cltr"])

    # # 6. Prints any tags that have been created for any of the sections:
    nbox.print_tag_rt("Tags", set(tag_exists), tag_created)


if __name__ == "__main__":
    main()
