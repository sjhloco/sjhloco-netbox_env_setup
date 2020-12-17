"""###### INPUT VALIDATE ######
Validates the formatting, value types and values within the input file used to build the NetBox environment.
All checks are done offline againt the file, is no communicaiton to NetBox
Some of the things it checks are:
-Main dictionaries (tenant, manufacturer, rir, role, crt_type, provider, cluster_type) and key is a list
-All mandatory dictionaires are present
-All Dictionary keys that are meant to be a list, integrar, boolean or IPv4 address are the correct format
-All referenced objects such as Tenant, site, rack_role, etc, exist within the input file
-Duplicate object names

To run the script refernnce the file with the input data. The file 'test.yml' will trigger the majority of formatting errors
python input_validate.py test.yml
"""

from pprint import pprint
import re
import ipaddress
from sys import argv
import yaml
from rich.console import Console
from rich.theme import Theme

class Input_validate():

    def __init__(self):
        with open(argv[1], 'r') as file_content:
            self.my_vars = yaml.load(file_content, Loader=yaml.FullLoader)
        # Used to know whether are any errors
        global are_errors
        are_errors = False

######################## Generic assert functions used by all classes to make it DRY ########################
    # STRING: Asserts that the variable is a string
    def assert_string(self, errors, variable, error_message):
        try:
            assert isinstance(variable, str), error_message
        except AssertionError as e:
            errors.append(str(e))
    # INTEGRER: Asserts that the variable is an integrer (number)
    def assert_integrer(self, errors, variable, error_message):
        try:
            assert isinstance(variable, int), error_message
        except AssertionError as e:
            errors.append(str(e))
    # LIST: Asserts that the variable is a list
    def assert_list(self, errors, variable, error_message):
        try:
            assert isinstance(variable, list), error_message
        except AssertionError as e:
            errors.append(str(e))
   # BOOLEAN: Asserts that the variable is True or False
    def assert_boolean(self, errors, variable, error_message):
        try:
            assert isinstance(variable, bool), error_message
        except AssertionError as e:
            errors.append(str(e))

  # REGEX: Matches the specified pattern at the beginning of the string
    def assert_regex_match(self, errors, regex, input_string, error_message):
        try:
            assert re.match(regex, input_string), error_message
        except AssertionError as e:
            errors.append(str(e))
    # IN: Asserts that the variable is within the specified value
    def assert_in(self, errors, variable, input_value, error_message):
        try:
            assert variable in input_value, error_message
        except AssertionError as e:
            errors.append(str(e))
    # EQUAL: Asserts that the variable does match the specified value
    def assert_equal(self, errors, variable, input_value, error_message):
        try:
            assert variable == input_value, error_message
        except AssertionError as e:
            errors.append(str(e))

    # IPv4: Asserts that the IPv4 Address or interface address are in the correct format
    def assert_ipv4(self, errors, variable, error_message):
        try:
            ipaddress.IPv4Interface(variable)
        except ipaddress.AddressValueError:
            errors.append(error_message)
        except ipaddress.NetmaskValueError:
            errors.append(error_message)

    # DUPLICATE: Asserts are no duplicate elements in a list, if so returns the duplicate in error message.
    def duplicate_in_list(self, errors, input_list, error_message, args):       # Args is a list of 0 to 4 args to use in error message before dup error
        dup = [i for i in set(input_list) if input_list.count(i) > 1]
        self.assert_equal(errors, len(dup), 0, error_message.format(*args, dup))
    # EXIST_LIST: Asserts the mandatory exists and is a list
    def assert_exist_list(self, errors, dict_key):
        try:
            assert self.my_vars.get(dict_key) != None, "[a]-{}:[/a] [i]{} dictionary is missing, this is a mandatory dictionary[/i]".format(
                                                        dict_key, dict_key.capitalize())
            assert isinstance(self.my_vars[dict_key], list), "[a]-{}:[/a] [i]{} must be a list[/i]".format(dict_key, dict_key.capitalize())
        except AssertionError as e:
            errors.append(str(e))

    # TNT_TAG: Asserts specified Tenant exists and Tag is a list
    def tnt_tag(self, errors, input_dict, key, input_tree, input_txt):
        self.assert_in(errors, input_dict.get('tenant', all_tnt[0]), all_tnt, "[a]-{}.tenant:[/a] [i]Tenant '{}' defined under {} '{}' does not exist, it "\
                       "should be pre-defined in the Organization dictionary[/i]".format(input_tree, input_dict.get('tenant'), input_txt, input_dict[key]))
        self.assert_list(errors, input_dict.get('tags', []), "[a]-{}.tags:[/a] [i]Tag '{}' for {} '{}' must be a list[/i]".format(input_tree, input_dict.get('tags'),
                         input_txt, input_dict[key]))
    # TNT_TAG_SITE_GRP: Asserts specified Tenant exists, site exists, Tag is a list and if defiend the Cluster group exists
    def tnt_tag_site_grp(self, errors, input_dict, key, input_tree, input_txt, all_cltr_grp):
        self.tnt_tag(errors, input_dict, key, input_tree, input_txt)
        self.assert_in(errors, input_dict.get('site', all_site[0]), all_site, "[a]-{}.site:[/a] [i]Site '{}' defined under {} '{}' does not exist, it should be "\
                      "pre-defined in the Organization dictionary[/i]".format(input_tree, input_dict.get('site'), input_txt, input_dict[key]))
        if input_dict.get('group') != None:
            self.assert_in(errors, input_dict['group'], all_cltr_grp, "[a]-{}.group:[/a] [i]Cluster-group '{}' defined under {} '{}' does not exist[/i]".format(
                           input_tree, input_dict.get('group'), input_txt, input_dict[key]))

    # RACK_RACK_GRP: Asserts Rack and Rack Group variables exist
    def assert_rack_rack_grp(self, org_errors, each_rack_grp, all_rack_roles, all_tnt, all_rack_grp, all_rack, each_tnt, each_site):
        if each_rack_grp.get('name') != None:
            all_rack_grp.append(each_rack_grp['name'])           # Creates a list of all rack groups
            # RACK: If rack exists must be a list and has a name
            if each_rack_grp.get('rack') != None:
                assert isinstance(each_rack_grp['rack'], list), "[a]-tenant.site.rack_grp.rack:[/a] [i]Rack in rack-group '{}' must be a list[/i]".format(each_rack_grp.get('name'))
                for each_rack in each_rack_grp['rack']:
                    if each_rack.get('name') != None:
                        all_rack.append(each_rack['name'])           # Creates a list of all racks
                        # RACK_ROLE: Assert that the rack role exists
                        self.assert_in(org_errors, each_rack.get('role', ''), all_rack_roles, "[a]-tenant.site.rack_grp.rack.rack_role:[/a] [i]Rack-role '{}' does "\
                                                                                              "not exist[/i]".format(each_rack.get('role')))
                        # RACK_HEIGHT: Must be an integrar
                        self.assert_integrer(org_errors, each_rack.get('height', 42), "[a]-tenant.site.rack_grp.rack.rack.height:[/a] [i]Height ('{}') of rack '{}' "\
                                                                                      "must be an integrar[/i]".format(each_rack.get('height'), each_rack['name']))
                        # RACK_TENANT: Assert that the specified tenant of the rack exists
                        self.assert_in(org_errors, each_rack.get('tenant', each_tnt['name']), all_tnt, "[a]-tenant.site.rack_grp.rack.rack.tenant:[/a] [i]Tenant '{}' "\
                                                                                    "of rack '{}' does not exist[/i]".format(each_rack.get('tenant'), each_rack['name']))
                        # RACK_TAG: If defined must be a list
                        self.assert_list(org_errors, each_rack.get('tags', []), "[a]-tenant.site.rack_grp.rack.rack.tags:[/a] [i]Tag '{}' for rack '{}' must be a list[/i]".
                                                                                 format(each_rack.get('tags'), each_rack['name']))
                    # RACK_NAME: Every rack group must have a name
                    elif each_rack.get('name') == None:
                        org_errors.append("[a]-tenant.site.rack_grp.rack.name:[/a] [i]A rack in rack-group '{}' is missing a name, this is a mandatory dictionary[/i]".
                                          format(each_rack_grp.get('name')))
        # RACK_GRP_NAME: Every rack-group must have a name
        elif each_rack_grp.get('name') == None:
            org_errors.append("[a]-tenant.site.rack_group.name:[/a] [i]A rack-group in site '{}' is missing a name, this is a mandatory dictionary[/i]".format(each_site.get('name')))

    # VRF_PREFIX: Asserts VRF and Prefix variables exist
    def assert_vrf_pfx(self, ipam_errors, input_dict, input_tree, all_vrf, all_vl_numb):
        if input_dict.get('vrf') != None:
            # VRF: Must be a list
            assert isinstance(input_dict['vrf'], list), "[a]-role.vlan_grp.vrf:[/a] [i]VRF within VLAN-group '{}' must be a list of sites[/i]".format(input_dict['name'])
            for each_vrf in input_dict['vrf']:
                all_pfx = []
                if each_vrf.get('name') != None:
                    all_vrf.append(each_vrf['name'])
                    # RD: Must be a string to stop : causing equations of the RD
                    self.assert_string(ipam_errors, each_vrf.get('rd', 'str'), "[a]-{}.vrf.rd:[/a] [i]The RD '{}' for VRF '{}' should be enclosed in quotes to make it a " \
                                                                               "string[/i]".format(input_tree, each_vrf.get('rd'), each_vrf['name']))
                    # UNIQUE: Must be True or False
                    self.assert_boolean(ipam_errors, each_vrf.get('unique', True), "[a]-{}.vrf.unique:[/a] [i]Unique '{}' in VRF '{}' is not valid, it must be boolean " \
                                                                                   "True or False[/i]".format(input_tree, each_vrf.get('unique'), each_vrf['name']))
                    # TNT_TAG: Asserts specified Tenant exists and Tag is a list
                    self.tnt_tag(ipam_errors, each_vrf, 'name', 'role.site.vlan_grp.vrf', 'VRF')
                    # PREFIX: A VRF must have a Prefix dictionary whose key is a list
                    assert each_vrf.get('prefix') != None, "[a]-{}.vrf.prefix:[/a] [i]VRF '{}' has no list of prefixes, this is a mandatory dictionary[/i]".format(input_tree, each_vrf['name'])
                    assert isinstance(each_vrf['prefix'], list), "[a]-{}.vrf.prefix:[/a] [i]Prefix within VRF '{}' must be a list[/i]".format(input_tree, each_vrf['name'])
                    for each_pfx in each_vrf['prefix']:
                        if each_pfx.get('pfx') != None:
                            # Adds prefixes to all_pfx list to check for duplciates if the VRF is set to only have unique prefixes
                            if each_vrf.get('unique', True) == True:
                                all_pfx.append(each_pfx['pfx'])
                            # PREFIX: Asserts it is a valid IPv4 address and subnet mask
                            self.assert_ipv4(ipam_errors, each_pfx['pfx'], "[a]-{}.vrf.prefix.pfx:[/a] [i]Prefix '{}' is not a valid IPv4 Address/Netmask[/i]".
                                                                            format(input_tree, each_pfx['pfx']))
                            if each_pfx.get('vl') != None:
                                # VLAN_EXIST: Assert that the specified site of the role exists (is in organisation dictionary)
                                self.assert_in(ipam_errors, each_pfx['vl'], all_vl_numb, "[a]-{}.vrf.prefix.vl:[/a] [i]VLAN '{}' of prefix '{}' does not exist, it should "\
                                                                                "be defined under the VLAN-group[/i]".format(input_tree, each_pfx['vl'], each_pfx['pfx']))
                            # POOL: Must be True or False
                            self.assert_boolean(ipam_errors, each_pfx.get('pool', False), "[a]-{}.vrf.prefix.pool:[/a] [i]Pool '{}' in prefix '{}' is not valid, it must "\
                                                                                    "be boolean True or False[/i]".format(input_tree, each_pfx.get('pool'), each_pfx['pfx']))
                            # TNT_TAG: Asserts specified Tenant exists and Tag is a list
                            self.tnt_tag(ipam_errors, each_pfx, 'pfx', input_tree + '.vrf.prefix', 'prefix')
                        elif each_pfx.get('pfx') == None:
                            ipam_errors.append("[a]-{}.vrf.prefix.pfx:[/a] [i]A prefix within VRF '{}' has no value, this is a mandatory dictionary[/i]".
                                                format(input_tree, each_vrf['name']))
                # VRF_NAME: Every VRF must have a name
                elif each_vrf.get('name') == None:
                    ipam_errors.append("[a]-{}.vrf.name:[/a] [i]A VRF within VLAN-group '{}' has no name, this is a mandatory dictionary[/i]".format(input_tree, input_dict['name']))
                # DUPLICATE_PFX: Prefixes within a VRFs should all be unique (if set to unique True)
                self.duplicate_in_list(ipam_errors, all_pfx, "[a]-{}:[/a] [i]There are duplicate {} {}, all prefixes should be unique within a VRF[/i]",
                                                             [input_tree + '.vrf.prefix', 'prefixes'])

    # PRINT_ERROR: Prints out any errors to screen
    def print_error(self, errors, section):
        global are_errors
        are_errors = True
        rc1.print("\n[a][b]{}:[/b] Check the contents of [i]'{}'[/i] for the following issues:[/a]".format(section, argv[1]))
        for err in errors:
            rc2.print(err)


######################## 1. PARENT DICTIONARY: Validate formatting of main dictionaries  ########################
    def parent_dict(self):
        # MAND: Makes sure that main dictionary for each section exists and is a list.
        parent_dict_err = []
        for parent_dict in ['tenant', 'manufacturer', 'rir', 'role', 'circuit_type', 'provider', 'cluster_type']:
            self.assert_exist_list(parent_dict_err, parent_dict)
        # FAILFAST: Exit script if dont exist or not a list as cant do further tests without these dict
        if len(parent_dict_err) != 0:
            self.print_error(parent_dict_err, 'PARENT DICTIONARY')
            exit()


######################## 2. ORGANISATION: Validate formatting of variables for objects within the Organisation menu ########################
    def org(self):
        global all_tnt, all_site
        org_errors, all_tnt, all_site, all_rack_grp, all_rack = ([] for i in range(5))
        all_rack_role = ['']           # needs to have an element as that is used as the default in get statements

        # RACK_ROLE: If rack role is defined asserts it is a list. If so checks that each dict has a name and creates a list of all rack-role names
        if self.my_vars['rack_role'] != None:
            try:
                assert isinstance(self.my_vars['rack_role'], list), "[a]-rack_role:[/a] [i]Rack-role must be a list[/i]"
                for each_rack_role in self.my_vars['rack_role']:
                    if each_rack_role.get('name') != None:
                        all_rack_role.append(each_rack_role['name'])
                    elif each_rack_role.get('name') == None:
                        org_errors.append("[a]-rack_role.name:[/a] [i]A rack-role is missing a name, this is a mandatory dictionary[/i]")
            except AssertionError as e:
                org_errors.append(str(e))

        # ALL_TNT: Create a list of all tenants names
        for each_tnt in self.my_vars['tenant']:
            if each_tnt.get('name') != None:
                all_tnt.append(each_tnt['name'])

        for each_tnt in self.my_vars['tenant']:
            try:
                # TNT_NAME: Every tenant must have a name
                assert each_tnt.get('name') != None, "[a]-tenant.name:[/a] [i]A tenant is missing a name, this is a mandatory dictionary[/i]"
                # TNT_TAG: If defined must be a list
                self.assert_list(org_errors, each_tnt.get('tags', []), "[a]-tenant.tags:[/a] [i]Tag '{}' for tenant '{}' must be a list[/i]".format(each_tnt.get('tags'), each_tnt['name']))
                if each_tnt.get('site') != None:
                    # SITE: If defined a site must be a list. If not failfast as cant do any of the further checks
                    assert isinstance(each_tnt['site'], list), "[a]-tenant.site:[/a] [i]Site in tenant '{}' must be a list[/i]".format(each_tnt.get('name'))
                    for each_site in each_tnt['site']:
                        if each_site.get('name') != None:
                            all_site.append(each_site['name'])           # Creates a list of all sites
                            # SITE_TAG: If defined must be a list
                            self.assert_list(org_errors, each_site.get('tags', []), "[a]-tenant.site.tags:[/a] [i]Tag '{}' for site '{}' must be a list[/i]".format(
                                                                                    each_site.get('tags'), each_site['name']))
                            # SITE_TIMEZONE: If defined must start with any of the defined Reagions, the location within that region can be anything
                            self.assert_regex_match(org_errors, '^(Africa\/|America\/|Asia\/|Australia\/|Canada\/|Europe\/|GMT\/|Indian\/|Pacific\/|US\/|UTC\/)', each_site.get(
                                                    'time_zone', 'UTC/'),"[a]-tenant.site.time_zone:[/a] [i]Time-zone '{}' for site '{}' is not a valid option, it must start " \
                                                    "with one of the pre-defined regions[/i]".format(each_site.get('time_zone'), each_site['name']))
                            # PARENT_RACK_GRP: Validates the parent rack group and racks
                            if each_site.get('rack_grp') != None:
                                # RACK_GRP: Must be a list
                                assert isinstance(each_site['rack_grp'], list), "[a]-tenant.site.rack_grp:[/a] [i]Rack-group in site '{}' must be a list[/i]".format(each_site.get('name'))
                                for each_parent_rack_grp in each_site['rack_grp']:
                                    self.assert_rack_rack_grp(org_errors, each_parent_rack_grp, all_rack_role, all_tnt, all_rack_grp, all_rack, each_tnt, each_site)
                                    # CHILD_RACK_GRP: If exists validates the child rack group and racks
                                    if each_parent_rack_grp.get('rack_grp') != None:
                                        assert isinstance(each_parent_rack_grp['rack_grp'], list), "[a]-tenant.site.rack_grp:[/a] [i]Nested rack-group in site '{}' must be a "\
                                                                                                    "list[/i]".format(each_site.get('name'))
                                        for each_child_rack_grp in each_parent_rack_grp['rack_grp']:
                                            self.assert_rack_rack_grp(org_errors, each_child_rack_grp, all_rack_role, all_tnt, all_rack_grp, all_rack, each_tnt, each_site)
                        # SITE_NAME: Every site must have a name
                        elif each_site.get('name') == None:
                            org_errors.append("[a]-tenant.site.name:[/a] [i]A site in tenant '{}' is missing a name, this is a mandatory dictionary[/i]".format(each_tnt['name']))
            except AssertionError as e:
                    org_errors.append(str(e))

        # DUPLICATE_OBJ_NAME: Rack Roles, Tenants, Sites, Rack-Groups and Racks should all have a unique name
        input_data = [(all_rack_role, 'rack-roles', 'rack_role.name'), (all_tnt, 'tenants', 'tenant.name'), (all_site, 'sites', 'tenant.site.name'),
             (all_rack_grp, 'rack-groups', 'tenant.site.rack_grp.name'), (all_rack, 'racks', 'tenant.site.rack_grp.rack.name')]
        for list_of_names, obj, err_msg in input_data:
            self.duplicate_in_list(org_errors, list_of_names, "[a]-{}:[/a] [i]There are duplicate {} with the same name {}, all names should be unique[/i]", [err_msg, obj])
        # ERROR: Prints error message of all issues found
        if len(org_errors) != 0:
            self.print_error(org_errors, 'ORGANISATION')


######################## 3. DEVICES: Validate formatting of variables for objects within the Devices menu ########################
    def dvc(self):
        dvc_errors, all_dev_roles, all_plfm, all_mftr = ([] for i in range(4))

        # DEVICE_ROLE: If device role is defined asserts it is a list. If so checks that each dict has a name and creates a list of all rack-role names
        if self.my_vars['device_role'] != None:
            try:
                assert isinstance(self.my_vars['device_role'], list), "[a]-device_role:[/a] [i]Device-role must be a list[/i]"
                for each_device_role in self.my_vars['device_role']:
                    if each_device_role.get('name') != None:
                        self.assert_boolean(dvc_errors, each_device_role.get('vm_role', False), "[a]-device_role.vm_role:[/a] [i]VM-role value '{}' in device-role '{}' " \
                                            "is not valid, it must be boolean True or False[/i]".format(each_device_role.get('vm_role'), each_device_role['name']))
                        all_dev_roles.append(each_device_role['name'])
                    elif each_device_role.get('name') == None:
                        dvc_errors.append("[a]-device_role.name:[/a] [i]A device-role is missing a name, this is a mandatory dictionary[/i]")
            except AssertionError as e:
                dvc_errors.append(str(e))

        for each_mftr in self.my_vars['manufacturer']:
            try:
                # MFTR_NAME: Every manufacturer must have a name
                assert each_mftr.get('name') != None, "[a]-manufacturer.name:[/a] [i]A manufacturer is missing a name, this is a mandatory dictionary[/i]"
                all_mftr.append(each_mftr['name'])
                if each_mftr.get('platform') != None:
                    # PLATFORM: If defined a platform must be a list. If not failfast as cant do any of the further checks
                    assert isinstance(each_mftr['platform'], list), "[a]-manufacturer.platform:[/a] [i]Platform in manufacturer '{}' must be a list[/i]".format(each_mftr.get('name'))
                    for each_platform in each_mftr['platform']:
                        # PLATFORM_NAME: Every site must have a name
                        if each_platform.get('name') == None:
                            dvc_errors.append("[a]-manufacturer.platform.name:[/a] [i]A platform in manufacturer '{}' is missing a name, this is a mandatory dictionary[/i]".format(each_mftr['name']))
                        elif each_platform.get('name') != None:
                            all_plfm.append(each_platform['name'])
                if each_mftr.get('device_type') != None:
                    # DVC_TYPE: If defined a Device type must be a list.
                    assert isinstance(each_mftr['device_type'], list), "[a]-manufacturer.device_type:[/a] [i]Device-type in manufacturer '{}' must be a list[/i]".format(each_mftr.get('name'))
            except AssertionError as e:
                    dvc_errors.append(str(e))

        # DUPLICATE_OBJ_NAME: Device Roles, Manufacturers and Platforms should all have a unique name
        input_data = [(all_dev_roles, 'device-roles', 'device_role.name'), (all_mftr, 'manufacturer', 'manufacturer.name'), (all_plfm, 'platforms', 'manufacturer.platform.name')]
        for list_of_names, obj, err_msg in input_data:
            self.duplicate_in_list(dvc_errors, list_of_names, "[a]-{}:[/a] [i]There are duplicate {} with the same name {}, all names should be unique[/i]", [err_msg, obj])
        # ERROR: Prints error message of all issues found
        if len(dvc_errors) != 0:
            self.print_error(dvc_errors, 'DEVICE')


######################## 4. IPAM: Validate formatting of variables for objects within the IPAM menu ########################
    def ipam(self):
        ipam_errors, all_rir, all_role = ([] for i in range(3))

        for each_rir in self.my_vars['rir']:
            try:
                # RIR_NAME: Every RIR must have a name
                assert each_rir.get('name') != None, "[a]-rir.name:[/a] [i]A RIR is missing a name, this is a mandatory dictionary[/i]"
                all_rir.append(each_rir['name'])
                self.assert_boolean(ipam_errors, each_rir.get('is_private', False), "[a]-rir.is_private:[/a] [i]Is_private '{}' in RIR '{}' is not valid, "\
                                            "it must be boolean True or False[/i]".format(each_rir.get('is_private'), each_rir['name']))
                if each_rir.get('ranges') != None:
                    # RIR_RANGES: If defined a platform must be a list. If not failfast as cant do any of the further checks
                    assert isinstance(each_rir['ranges'], list), "[a]-rir.ranges:[/a] [i]Ranges in RIR '{}' must be a list[/i]".format(each_rir.get('name'))
                    for each_range in each_rir['ranges']:
                        # RIR_PREFIX: Must be defined and a valid IPv4 address
                        if each_range.get('prefix') != None:
                            self.assert_ipv4(ipam_errors, each_range['prefix'], "[a]-rir.ranges.prefix:[/a] [i]Prefix '{}' is not a valid IPv4 Address/Netmask[/i]".format(each_range['prefix']))
                            # RIR_TAG: If defined must be a list
                            self.assert_list(ipam_errors, each_range.get('tags', []), "[a]-rir.ranges.tags:[/a] [i]Tag '{}' for prefix '{}' must be a list[/i]".format(each_range.get('tags'), each_range['prefix']))
                        elif each_range.get('prefix') == None:
                            ipam_errors.append("[a]-rir.ranges.prefix:[/a] [i]A prefix is missing for one of the ranges in RIR '{}', this is a mandatory dictionary[/i]".format(each_rir['name']))
            except AssertionError as e:
                    ipam_errors.append(str(e))

        for each_role in self.my_vars['role']:
            try:
                # ROLE_NAME: Every Role must have a name
                assert each_role.get('name') != None, "[a]-role.name:[/a] [i]A prefix/VLAN-role is missing a name, this is a mandatory dictionary[/i]"
                all_role.append(each_role['name'])
                # ROLE_SITE: A role must have a site dictionary whose key is a list
                assert each_role.get('site') != None, "[a]-role.site:[/a] [i]Prefix/VLAN-role '{}' has no list of sites, this is a mandatory dictionary[/i]".format(each_role['name'])
                assert isinstance(each_role['site'], list), "[a]-role.site:[/a] [i]Site within role '{}' must be a list of sites[/i]".format(each_role['name'])
                for each_site in each_role['site']:
                    all_vl_grp, all_vrf = ([] for i in range(2))        # Used to check for duplicates, a VRF or VLAN Group is unique to a site
                    if each_site.get('name') != None:
                       # SITE_EXIST: Assert that the specified site of the role exists (is in organisation dictionary)
                        self.assert_in(ipam_errors, each_site['name'], all_site, "[a]-role.site.name:[/a] [i]Site '{}' in prefix/VLAN-role '{}' does not exist, it should be "\
                                                                                 "pre-defined in the Organization dictionary[/i]".format(each_site['name'], each_role['name']))
                        # VLAN_PFX_TAG: If defined must be a list
                        self.assert_list(ipam_errors, each_site.get('tags', []), "[a]-role.site.tags:[/a] [i]Tag '{}' for all prefixes/VLANs in site '{}' must be a list[/i]".
                                                                                  format(each_site.get('tags'), each_site['name']))
                        if each_site.get('vlan_grp') != None:
                            # VLAN_GRP: Must be a list
                            assert isinstance(each_site['vlan_grp'], list), "[a]-role.site.vlan_grp:[/a] [i]VLAN-group within Site '{}' must be a list[/i]".format(each_site['name'])
                            for each_vl_grp in each_site['vlan_grp']:
                                all_vl_name, all_vl_numb = ([] for i in range(2))             # Used to check for duplicates, a VLAN is unique to a VLAN Group
                                if each_vl_grp.get('name') != None:
                                    all_vl_grp.append(each_vl_grp['name'])
                                    self.tnt_tag(ipam_errors, each_vl_grp, 'name', 'role.site.vlan_grp', 'VLAN-group')
                                    if each_vl_grp.get('vlan') != None:
                                        # VLAN: Must be a list
                                        assert isinstance(each_vl_grp['vlan'], list), "[a]-role.site.vlan_grp.vlan:[/a] [i]VLAN within VLAN-group '{}' must be a list[/i]".format(each_vl_grp['name'])
                                        for each_vl in each_vl_grp['vlan']:
                                            if each_vl.get('name') != None:
                                                all_vl_name.append(each_vl['name'])
                                                if each_vl.get('id') != None:
                                                    all_vl_numb.append(each_vl['id'])
                                                    # VLAN_ID: Must exist and be an integrar
                                                    self.assert_integrer(ipam_errors, each_vl.get('id'), "[a]-role.site.vlan_grp.vlan.id:[/a] [i]VLAN id '{}' of VLAN-group '{}' "\
                                                                                                          "must be an integrar[/i]".format(each_vl.get('id'), each_vl_grp['name']))
                                                elif each_vl.get('id') == None:
                                                    ipam_errors.append("[a]-role.site.vlan_grp.vlan.id:[/a] [i]VLAN '{}' has no VLAN id, this is a mandatory dictionary[/i]".format(each_vl['name']))
                                                self.tnt_tag(ipam_errors, each_vl, 'name', 'role.site.vlan_grp.vlan', 'VLAN')
                                            # VLAN_NAME: Every Group must have a name
                                            elif each_vl.get('name') == None:
                                                ipam_errors.append("[a]-role.site.vlan_grp.vlan.name:[/a] [i]A VLAN within VLAN-group '{}' has no name, this is a mandatory "\
                                                                    "dictionary[/i]".format(each_vl_grp['name']))
                                         # VRF_PREFIX: Asserts VRF and Prefix variables exist for VRFs under the VLAN Group (prefxies associated to VLANs like physical site)
                                        self.assert_vrf_pfx(ipam_errors, each_vl_grp, 'role.site.vlan_grp', all_vrf, all_vl_numb)
                                # VLAN_GRP_NAME: Every VLAN Group must have a name
                                elif each_vl_grp.get('name') == None:
                                    ipam_errors.append("[a]-role.site.vlan_grp.name:[/a] [i]A VLAN-group within site '{}' has no name, this is a mandatory dictionary[/i]".format(each_site['name']))
                                # DUPLICATE_VLAN: VLAN names and Numbers within a VLAN group should all be unique
                                self.duplicate_in_list(ipam_errors, all_vl_name, "[a]-{}:[/a] [i]There are duplicate {} with the same name {}, all names should be unique within "\
                                                                                 "a VLAN-group[/i]",['role.site.vlan_grp.vlan.name', 'VLANs'])
                                self.duplicate_in_list(ipam_errors, all_vl_numb, "[a]-{}:[/a] [i]There are duplicate {} with the same ID '{}', all IDs should be unique within "\
                                                                                 "a VLAN-group[/i]", ['role.site.vlan_grp.vlan.id', 'VLANs'])
                        # VRF_PREFIX: Asserts VRF and Prefix variables exist for VRFs not associated to VLANs (such as cloud prefixes)
                        self.assert_vrf_pfx(ipam_errors, each_site, 'role.site.vlan_grp', all_vrf, [])
                    # SITE_NAME: Every site must have a name
                    elif each_site.get('name') == None:
                        ipam_errors.append("[a]-role.site.name:[/a] [i]A site in prefix/VLAN-role '{}' is missing a name, this is a mandatory dictionary[/i]".format(each_role['name']))
                    # DUPLICATE_VRF: VRFs within a site should all be unique
                    self.duplicate_in_list(ipam_errors, all_vrf, "[a]-{}:[/a] [i]There are duplicate {} with the same name {}, all names should be unique within a site[/i]",
                                                                 ['role.site.vlan_grp.vrf.name', 'VRFs'])
            except AssertionError as e:
                    ipam_errors.append(str(e))

        # DUPLICATE_OBJ_NAME: RIRs and Roles should all have a unique name
        self.duplicate_in_list(ipam_errors, all_rir, "[a]-{}:[/a] [i]There are duplicate {} with the same name {}, all names should be unique[/i]", ['rir.name', 'RIRs'])
        self.duplicate_in_list(ipam_errors, all_role, "[a]-{}:[/a] [i]There are duplicate {} with the same name {}, all names should be unique[/i]", ['role.name', 'prefix/VLAN-roles'])
       # ERROR: Prints error message of all issues found
        if len(ipam_errors) != 0:
            self.print_error(ipam_errors, 'IPAM')


######################## 5. CIRCUITS: Validate formatting of variables for objects within the Circuits menu ########################
    def crt(self):
        crt_errors, all_crt_type, all_pvdr, all_cid = ([] for i in range(4))

         # CIRCUIT_TYPE: Checks that each dict has a name and creates a list of all rack-role names
        for each_crt_type in self.my_vars['circuit_type']:
            try:
                assert each_crt_type.get('name') != None, "[a]-circuit_type.name:[/a] [i]A circuit-type is missing a name, this is a mandatory dictionary[/i]"
                all_crt_type.append(each_crt_type['name'])
            except AssertionError as e:
                crt_errors.append(str(e))

        for each_pvdr in self.my_vars['provider']:
            try:
                # PVDR_NAME: Every provider must have a name
                assert each_pvdr.get('name') != None, "[a]-provider.name:[/a] [i]A provider is missing a name, this is a mandatory dictionary[/i]"
                all_pvdr.append(each_pvdr['name'])
                # ASN: Must be an integrar
                self.assert_integrer(crt_errors, each_pvdr.get('asn', 1), "[a]-provider.asn:[/a] [i]ASN ('{}') of provider '{}' must be an integrar[/i]".
                                                                           format(each_pvdr.get('asn'), each_pvdr['name']))
                # TAG: If defined must be a list
                self.assert_list(crt_errors, each_pvdr.get('tags', []), "[a]-provider.tags:[/a] [i]Tag '{}' for provider '{}' must be a list[/i]".
                                                                         format(each_pvdr.get('tags'), each_pvdr['name']))
                assert each_pvdr.get('circuit') != None, "[a]-provider.circuit:[/a] [i]Provider '{}' has no list of circuits, this is a mandatory "\
                                                          "dictionary[/i]".format(each_pvdr['name'])
                assert isinstance(each_pvdr['circuit'], list), "[a]-provider.circuit:[/a] [i]Circuit in provider '{}' must be a list[/i]".format(each_pvdr.get('name'))
                for each_crt in each_pvdr['circuit']:
                    if each_crt.get('cid') != None:
                        all_cid.append(each_crt['cid'])
                        # CRT_TYPE: Must be from the pre-defined types
                        self.assert_in(crt_errors, each_crt.get('type', all_crt_type[0]), all_crt_type, "[a]-provider.circuit.type:[/a] [i]Circuit-type '{}' for circuit "\
                                                                                                         "'{}' does not exist[/i]".format(each_crt.get('type'), each_crt['cid']))
                        # CMT_RATE: Commit Rate must be an integrar
                        self.assert_integrer(crt_errors, each_crt.get('commit_rate', 10), "[a]-provider.circuit.commit_rate:[/a] [i]Commit-rate ('{}') of circuit '{}' "\
                                                                                          "must be an integrar[/i]".format(each_crt.get('commit_rate'), each_crt['cid']))
                        # TNT_TAG: Asserts specified Tenant exists and Tag is a list
                        self.tnt_tag(crt_errors, each_crt, 'cid', 'provider.circuit', 'circuit')
                    # CRT_CID: Every Circuit must have a CID/name
                    elif each_crt.get('cid') == None:
                        crt_errors.append("[a]-provider.circuit.name:[/a] [i]A Circuit in provider '{}' is missing a name, this is a mandatory dictionary[/i]".format(each_pvdr['name']))
            except AssertionError as e:
                    crt_errors.append(str(e))

        # DUPLICATE_OBJ_NAME: Circuit Types, Providers and CIDs should all have a unique name
        self.duplicate_in_list(crt_errors, all_crt_type, "[a]-{}:[/a] [i]There are duplicate {} with the same name {}, all names should be unique[/i]", ['crt_type.name', 'circuit-types'])
        self.duplicate_in_list(crt_errors, all_pvdr, "[a]-{}:[/a] [i]There are duplicate {} with the same name {}, all names should be unique[/i]", ['provider.name', 'providers'])
        self.duplicate_in_list(crt_errors, all_cid, "[a]-{}:[/a] [i]There are duplicate {} with the same CID {}, all CIDs should be unique[/i]", ['provider.circuit.cid', 'circuits'])
        # ERROR: Prints error message of all issues found
        if len(crt_errors) != 0:
            self.print_error(crt_errors, 'CIRCUIT')


######################## 6. VIRTUAL: Validate formatting of variables for objects within the virtualization menu ########################
    def vrtl(self):
        vrtl_errors, all_cltr_grp, all_cltr_type, all_cltr = ([] for i in range(4))

       # CLUSTER_GRP: If cluster_role is defined asserts it is a list, checks that each dict has a name and creates a list of all cluster group names
        if self.my_vars['cluster_group'] != None:
            try:
                assert isinstance(self.my_vars['cluster_group'], list), "[a]-cluster_group:[/a] [i]Cluster-group must be a list[/i]"
                for each_cltr_grp in self.my_vars['cluster_group']:
                    if each_cltr_grp.get('name') != None:
                        all_cltr_grp.append(each_cltr_grp['name'])
                    elif  each_cltr_grp.get('name') == None:
                        vrtl_errors.append("[a]-cluster_group.name:[/a] [i]A cluster-group is missing a name, this is a mandatory dictionary[/i]")
            except AssertionError as e:
                vrtl_errors.append(str(e))

        for each_cltr_type in self.my_vars['cluster_type']:
            try:
                # CLTR_TYPE_NAME: Every Cluster Type must have a name
                assert each_cltr_type.get('name') != None, "[a]-cluster_type.name:[/a] [i]A cluster-type is missing a name, this is a mandatory dictionary[/i]"
                all_cltr_type.append(each_cltr_type['name'])
                self.tnt_tag_site_grp(vrtl_errors, each_cltr_type, 'name', 'cluster_type', 'cluster-type', all_cltr_grp)
                if each_cltr_type.get('cluster') != None:
                    assert isinstance(each_cltr_type['cluster'], list), "[a]-cluster_type.cluster:[/a] [i]Cluster in cluster-type '{}' must be a list[/i]".format(each_cltr_type['name'])
                    for each_cltr in each_cltr_type['cluster']:
                        if each_cltr.get('name') != None:
                            all_cltr.append(each_cltr['name'])
                            self.tnt_tag_site_grp(vrtl_errors, each_cltr, 'name', 'cluster_type.cluster', 'cluster', all_cltr_grp)
                        elif each_cltr.get('name') == None:
                            vrtl_errors.append("[a]-cluster_group.cluster.name:[/a] [i]A cluster in cluster-type '{}' is missing a name, this is a mandatory dictionary[/i]".format(each_cltr_type['name']))
            except AssertionError as e:
                vrtl_errors.append(str(e))

        # DUPLICATE_OBJ_NAME: Circuit Types, Providers and CIDs should all have a unique name
        self.duplicate_in_list(vrtl_errors, all_cltr_grp, "[a]-{}:[/a] [i]There are duplicate {} with the same name {}, all names should be unique[/i]", ['cluster_group.name', 'cluster-groups'])
        self.duplicate_in_list(vrtl_errors, all_cltr_type, "[a]-{}:[/a] [i]There are duplicate {} with the same name {}, all names should be unique[/i]", ['cluster_type.name', 'cluster-types'])
        self.duplicate_in_list(vrtl_errors, all_cltr, "[a]-{}:[/a] [i]There are duplicate {} with the same name {}, all names should be unique[/i]", ['cluster_type.cluster.name', 'clusters'])
        # ERROR: Prints error message of all issues found
        if len(vrtl_errors) != 0:
            self.print_error(vrtl_errors, 'VIRTUALIZATION')


######################## ENGINE: Runs the methods of the script ########################

def main():
    # Rich formatting
    global rc1, rc2
    rc1 = Console(theme=Theme({'a': "#2471A3"}))
    rc2 = Console(theme=Theme({'repr.str': 'i #A93226', 'repr.number': 'i #A93226', 'a': 'i b #000000'}))

    script, first = argv
    validate = Input_validate()

    #1. PARENT: Validate formatting of main mandatory dictionaries
    validate.parent_dict()
    #2. ORG: Validate formatting of Organisation menu dictionaries
    validate.org()
    #3. DEVICES: Validate formatting of Device menu dictionaries
    validate.dvc()
    #4. IPAM: Validate formatting of IPAM menu dictionaries
    validate.ipam()
    #5. CIRCUITS: Validate formatting of Circuit menu dictionaries
    validate.crt()
    #6. VIRTUAL: Validate formatting of Virtualization menu dictionaries
    validate.vrtl()

    if are_errors == False:
        rc2.print("[#000000]No errors found in the input file, use [i #0AC92B]'python nbox_env_setup.py {}'[/i #0AC92B] to build the NetBox environment.[/#000000]".format(argv[1]))

if __name__ == '__main__':
    main()