"""
## Netbox Base - Setup the base netbox environment
Creates the environment within NetBox ready for adding devices, it does not add the devices themselves.
This script is not idempotent. Its purpose to add objects rather than edit or delete existing objects.
The environment is defined in YAML files (opens all from defined directory) that follows the hierarchical structure of NetBox.

2. ORG_TNT_SITE_RACK: Create all the organisation objects
3. DVC_MTFR_TYPE: Create all the objects required to create devices
4. IPAM_VRF_VLAN: Create all the IPAM objects
5. CRT_PVDR: Create all the Circuit objects
6. VIRTUAL: Creates all the Cluster objects
7. CONTACT: Creates all the Contacts and associates them to objects

It is advisable to run the validation script against the input file to ensure the formatting of the input file is correct
python input_validate.py test.yml

When run pass in directory where yaml files are stored. Without flags will try and create all objects or can limit it using flags (-o, -d, -i, -p, -v, -c)
python nbox_env_setup.py simple_example
"""

import config
import argparse
from collections import defaultdict
from typing import Any, Dict
import sys
import yaml
import os
from rich.console import Console
from rich.theme import Theme
import ipdb

from netbox import Nbox
from dm import Organisation
from dm import Devices
from dm import Ipam
from dm import Circuits
from dm import Virtualisation
from dm import Contacts

# ----------------------------------------------------------------------------
# Variables to change dependant on environment
# ----------------------------------------------------------------------------
# Directory that holds all device type templates
dvc_type_dir = os.path.join(os.getcwd(), "device_type")
input_dir = "full_example"
base_dir = os.getcwd()

# Netbox login details, token (api_token) is stored in non github shared config.py file (create token your user profile or in admin for other users)
# netbox_url = "https://10.10.10.101"
# netbox_url = "http://10.10.10.104:8000/"
# netbox_url = "http://10.30.10.104:8000/"
netbox_url = "http://10.103.40.120:8000/"
token = config.api_token

# If using Self-signed cert must have been signed by a CA (can all be done on same box in opnessl) and this points to that CA cert
# os.environ["REQUESTS_CA_BUNDLE"] = os.path.expanduser(
#     "~/Documents/Coding/Netbox/nbox_py_scripts/myCA.pem"
# )


# ----------------------------------------------------------------------------
# 1. Gathers input arguments as well as loading and validating the input file
# ----------------------------------------------------------------------------
class Inputs:
    def __init__(self) -> Dict[str, Any]:
        my_theme = {"repr.ipv4": "none", "repr.number": "none", "repr.call": "none"}
        self.rc = Console(theme=Theme(my_theme))

    # 1a. ARG: Gather input args and file name
    def arg_parser(self) -> Dict[str, Any]:
        args = argparse.ArgumentParser()
        args.add_argument(
            "-o",
            "--organisation",
            action="store_true",
            help="Create all Netbox Organisation objects",
        )
        args.add_argument(
            "-d",
            "--device",
            action="store_true",
            help="Create all Netbox Device objects",
        )
        args.add_argument(
            "-i",
            "--ipam",
            action="store_true",
            help="Create all Netbox IPAM objects",
        )
        args.add_argument(
            "-p",
            "--provider",
            action="store_true",
            help="Create all Netbox Provider objects",
        )
        args.add_argument(
            "-c",
            "--contact",
            action="store_true",
            help="Create all Netbox Contact objects and assignments",
        )
        args.add_argument(
            "-v",
            "--virtual",
            action="store_true",
            help="Create all Netbox Virtualisation objects",
        )
        # parse_known_args allows filename to be entered without needing a flag (arg)
        all_args, directory = args.parse_known_args()

        if len(directory) != 0:
            tmp_input_dir = directory[0]
        elif len(directory) == 0:
            tmp_input_dir = input_dir
        return vars(all_args), tmp_input_dir

    # 1b. FILE: Loads input file and validates it
    def input_val(self, input_dir: str, args: Dict[str, Any]) -> Dict[str, Any]:
        # VAL_DIR: Check directory exists incurrent location or base directory
        if os.path.exists(input_dir) == False:
            if os.path.exists(os.path.join(base_dir, input_dir)) == False:
                self.rc.print(
                    f":x: Input File Error - Input file directories '{os.path.join(os.getcwd(), input_dir)}' "
                    f"or '{os.path.join(base_dir, input_dir)}' do not exist."
                )
                sys.exit(1)
            else:
                input_dir = os.path.join(base_dir, input_dir)

        # LOAD_FILE: Load the variable files
        my_vars = {}
        for filename in os.listdir(input_dir):
            with open(os.path.join(input_dir, filename), "r") as file_content:
                my_vars.update(yaml.load(file_content, Loader=yaml.FullLoader))
        # VAL_FILE: Validates the input dicts needed for the specified flags are present
        val = dict(
            organisation=("tenant", "rack_role"),
            device=("device_role", "manufacturer"),
            ipam=("rir", "role"),
            provider=("circuit_type", "provider"),
            virtual=("cluster_group", "cluster_type"),
            contact=("contact_role", "contact_group", "contact_assign"),
        )
        error = defaultdict(list)
        for flag, dicts in val.items():
            if args[flag] != False:
                for each_dict in dicts:
                    try:
                        assert my_vars.get(each_dict) != None
                    except AssertionError:
                        error[flag].append(each_dict)
        if len(error) != 0:
            for flag, dicts in error.items():
                self.rc.print(
                    f":x: Input Error - The input flag '{flag}' requires dictionaries '{', '.join(list(dicts))}' in the input files"
                )
            sys.exit(1)
        elif len(error) == 0:
            return my_vars


# ----------------------------------------------------------------------------
# ENGINE: Runs the methods of the script, first creating data-model and using to create non-existant objects
# ----------------------------------------------------------------------------
def main():
    # 1. ARG_FILE_NBOX: Gathers input flags (args), input file variables (dicts) and initialises the Netbox connection (nbox)
    arg_vars = Inputs()
    args, input_dir = arg_vars.arg_parser()
    my_vars = arg_vars.input_val(input_dir, args)
    # Initialise Netbox class used to run Netbox API calls
    tag_exists, tag_created, rt_exists, rt_created = ([] for i in range(4))
    nbox = Nbox(netbox_url, token, tag_exists, tag_created, rt_exists, rt_created)
    # Used to run all object creation classes if no flags input
    flag_all = False
    for flag_bool in args.values():
        flag_all = flag_all + flag_bool

    # 2. ORG_TNT_SITE_RACK: Create all the organisation objects
    if args["organisation"] == True or flag_all == False:
        org = Organisation(nbox, my_vars["tenant"], my_vars["rack_role"])
        org_dict = org.create_tnt_site_rack()
        # Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
        nbox.engine("Rack Role", "dcim.rack_roles", "name", org_dict["rack_role"])
        nbox.engine("Tenant", "tenancy.tenants", "name", org_dict["tnt"])
        nbox.engine("Site", "dcim.sites", "name", org_dict["site"])
        nbox.engine("Location (parent)", "dcim.locations", "slug", org_dict["prnt_loc"])
        nbox.engine("Location (child)", "dcim.locations", "slug", org_dict["chld_loc"])
        nbox.engine("Rack", "dcim.racks", "name", org_dict["rack"])

    # 3. DVC_MTFR_TYPE: Create all the objects required to create devices
    if args["device"] == True or flag_all == False:
        dvc = Devices(
            nbox, my_vars["device_role"], my_vars["manufacturer"], dvc_type_dir
        )
        dvc_dict = dvc.create_dvc_type_role()
        # Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
        nbox.engine("Device-role", "dcim.device_roles", "name", dvc_dict["dev_role"])
        nbox.engine("Manufacturer", "dcim.manufacturers", "name", dvc_dict["mftr"])
        nbox.engine("Platform", "dcim.platforms", "name", dvc_dict["pltm"])
        nbox.engine("Device-type", "dcim.device_types", "model", dvc_dict["dev_type"])

    # 4. IPAM_VRF_VLAN: Create all the IPAM objects
    if args["ipam"] == True or flag_all == False:
        ipam = Ipam(nbox, my_vars["rir"], my_vars["role"])
        ipam_dict = ipam.create_ipam()

        # Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
        nbox.engine("RIRs", "ipam.rirs", "name", ipam_dict["rir"])
        nbox.engine("Aggregates", "ipam.aggregates", "prefix", ipam_dict["aggr"])
        nbox.engine("Prefix/VLAN Role", "ipam.roles", "name", ipam_dict["role"])
        nbox.engine("VLAN Group", "ipam.vlan-groups", "name", ipam_dict["vlan_grp"])
        nbox.engine("VRF", "ipam.vrfs", "name", ipam_dict["vrf"])
        nbox.print_tag_rt("Route-Targets", set(rt_exists), rt_created)
        # First check if VL/PFX exist in VL_GRP/VRF, then if exist in ROLE.
        nbox.engine(
            "VLAN",
            ["ipam.vlans", "ipam.vlan_groups"],
            ["name", "group_id"],
            ipam_dict["vlan"],
        )
        nbox.engine(
            "Prefix",
            ["ipam.prefixes", "ipam.vrfs"],
            ["prefix", "vrf_id"],
            ipam_dict["prefix"],
        )

    # 5. CRT_PVDR: Create all the Circuit objects
    if args["provider"] == True or flag_all == False:
        crt = Circuits(nbox, my_vars["circuit_type"], my_vars["provider"])
        crt_dict = crt.create_crt_pvdr()
        # Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
        nbox.engine(
            "Circuit Type", "circuits.circuit-types", "name", crt_dict["crt_type"]
        )
        nbox.engine("Provider", "circuits.providers", "name", crt_dict["pvdr"])
        nbox.engine("Circuit", "circuits.circuits", "cid", crt_dict["crt"])

    # 6. VIRTUAL: Creates all the Cluster objects
    if args["virtual"] == True or flag_all == False:
        vrtl = Virtualisation(nbox, my_vars["cluster_group"], my_vars["cluster_type"])
        vrtl_dict = vrtl.create_vrtl()
        # Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
        nbox.engine(
            "Cluster Type",
            "virtualization.cluster-types",
            "name",
            vrtl_dict["cltr_type"],
        )
        nbox.engine(
            "Cluster Group",
            "virtualization.cluster-groups",
            "name",
            vrtl_dict["cltr_grp"],
        )
        nbox.engine("Cluster", "virtualization.clusters", "name", vrtl_dict["cltr"])

    # 7. CONTACTS: Creates all the contacts and assigns to objects
    if args["contact"] == True or flag_all == False:
        cnt = Contacts(
            nbox,
            my_vars["contact_role"],
            my_vars["contact_group"],
            my_vars["contact_assign"],
        )
        cnt_dict = cnt.create_contact()
        nbox.engine(
            "Contact Role", "tenancy.contact-roles", "name", cnt_dict["cnt_role"]
        )
        nbox.engine(
            "Contact Group", "tenancy.contact-groups", "name", cnt_dict["cnt_grp"]
        )
        nbox.engine("Contacts", "tenancy.contacts", "name", cnt_dict["cnt"])
        nbox.engine(
            "Contact Assignment",
            "tenancy.contact-assignments",
            "multi-fltr",
            cnt_dict["cnt_asgn"],
        )

    # 8. Prints any tags that have been created for any of the sections:
    nbox.print_tag_rt("Tags", set(tag_exists), tag_created)


if __name__ == "__main__":
    main()
