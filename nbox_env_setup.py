"""
###### Netbox Base - Setup the base netbox environment ######
Creates the environment within NetBox ready for adding devices, it does not add the devices themselves.
This script is not idempotent. Its purpose to add objects rather than edit or delete existing objects.
The environment is defined in a YAML file that follows the hierarchical structure of NetBox.
The script also follows this structure allowing for subsections of the environment to be created or additions to an already pre-existing environment.

Under the engine you can hash out a seciton so it only runs the sectiosn you want to create objects for.
-1. ORG_TNT_SITE_RACK: Create all the organisation objects
-2. DVC_MTFR_TYPE: Create all the objects required to create devices
-3. IPAM_VRF_VLAN: Create all the IPAM objects
-4. CRT_PVDR: Create all the Circuit objects
-5. VIRTUAL: Creates all the Cluster objects

It is advisable to run the validation script against the input file to ensure the formatting of the input file is correct
python input_validate.py test.yml
python nbox_env_setup.py simple_example.yml
"""

import config
import pynetbox
from pynetbox.core.query import RequestError
import yaml
import operator
import os
import ast
from sys import argv
import os

 ######################## Variables to change dependant on environment ########################
# Directory that holds all device type templates
dvc_type_dir = os.path.expanduser('~/Documents/Coding/Netbox/nbox_py_scripts/nbox_env_setup/device_type')

# Netbox login details (create from your user profile or in admin for other users)
netbox_url = "https://10.10.10.101"
token = config.api_token
# If using Self-signed cert must have been signed by a CA (can all be done on same box in opnessl) and this points to that CA cert
os.environ['REQUESTS_CA_BUNDLE'] = os.path.expanduser('~/Documents/Coding/Netbox/nbox_py_scripts/myCA.pem')


############################ INZT_LOAD: Opens netbox connection and loads the variable file ############################
class Nbox():
    def __init__(self):
        self.nb = pynetbox.api(url=netbox_url, token=token)
        with open(argv[1], 'r') as file_content:
            self.my_vars = yaml.load(file_content, Loader=yaml.FullLoader)


############################ OBJ_CHECK: API call to check if objects already exists in Netbox ############################
    def obj_check(self, output_name, api_attr, obj_fltr, obj_dm):     # for example Tenants, tenancy.tenants, tnt, name
        # NEW_DMs: Creates 2 lists of DMs based on whether the object already exists or not
        obj_notexist_dm, obj_exist_name = ([] for i in range(2))

        for each_obj_dm in obj_dm:
            if operator.attrgetter(api_attr)(self.nb).get(**{obj_fltr: each_obj_dm[obj_fltr]}) == None:
                obj_notexist_dm.append(each_obj_dm)
            else:
                obj_exist_name.append(each_obj_dm[obj_fltr])
        if output_name == 'Device-type':
            self.dev_type_create(output_name, api_attr, obj_notexist_dm, obj_exist_name)
        else:
            self.obj_create(output_name, api_attr, obj_notexist_dm, obj_exist_name)


############################ OBJ_CREATE: API engine to create objects or error based on the details fed into it ############################
    def obj_create(self, output_name, api_attr, obj_notexist_dm, obj_exist_name):
        #1. ADD_OBJ: If not already present adds the object. If for any reason fails returns error message
        if len(obj_notexist_dm) != 0:
            try:
                result = operator.attrgetter(api_attr)(self.nb).create(obj_notexist_dm)
            except RequestError as e:
                # Error message is a string but has the formt of list of dicts, literal_eval converts back into a list
                err_msg = ast.literal_eval(e.error)
                for err in err_msg:
                    if len(err) != 0:            # safe guards against empty dicts returned in the error message
                        print("{} {}: {} - {}".format(u'\u274c', output_name, list(err.keys())[0], list(err.values())[0]))
        #2. RETURN: Message returned (as long as no errors)
        if len(obj_exist_name) != 0:
            print('{}  {}: {} already exist'.format(u'\u26A0\uFE0F', output_name, str(obj_exist_name).replace('[', '').replace(']', '')))
        if 'result' in locals():       # only triggered if results exist (try/except run)
            print("{} {}: '{}' successfully created".format(u'\u2705', output_name, str(result).replace('[', '').replace(']', '')))


############################ DEV_TYPE_CREATE: device_type needs custom call due to its components (intf, power, etc) ############################
    def dev_type_create(self, output_name, api_attr, obj_notexist_dm, obj_exist_name):
        all_result = []
        # ADD_OBJ: If not already present adds the device_type. If any of the components fallsback and deletes the device_type that was added
        if len(obj_notexist_dm) != 0:
            # Dict of components with freindly name for err_message and component api url
            component = dict(interface='interface_templates', power='power_port_templates', console='console_port_templates',
                             rear_port='rear_port_templates', front_port='front_port_templates')
            for each_type in obj_notexist_dm:
                # 1. Tries to create the device_type, if fails returns error message
                try:
                    result = operator.attrgetter(api_attr)(self.nb).create(each_type)
                    # 2a. If dev_type creation suceeds tries to create each device_type component
                    try:
                        for obj, comp_api_attr in component.items():
                            if len(each_type[obj]) != 0:
                                if obj != 'front_port':
                                    operator.attrgetter(comp_api_attr)(self.nb.dcim).create(each_type[obj])
                                # Front-port needs the rear-port ID (as name is shared) map to it when created
                                else:
                                    # First needs to get the device_type ID which in turn is used to get the rear_port ID and add to the dict used to create component
                                    dev_type_id = self.nb.dcim.device_types.get(slug=each_type['slug']).id
                                    for each_port in each_type[obj]:
                                        each_port['rear_port']= self.nb.dcim.rear_port_templates.filter(name=each_port['name'], devicetype_id=dev_type_id)[0].id
                                    operator.attrgetter(comp_api_attr)(self.nb.dcim).create(each_type[obj])
                        # If all components added successfully adds result to list to tell user that the device_type was created
                        all_result.append(result)
                    # 2b. If any of the componets fail displays an error message about the component and deletes the device_type
                    except RequestError as e:
                        err_msg = ast.literal_eval(e.error)
                        error = []
                        for err in err_msg:
                            if len(err) != 0:
                                error.append(err)
                        print("{} {}: Failed to create '{}' because of errors with '{}' component - {}".format(u'\u274c', output_name, each_type['model'], obj, error))
                        self.nb.dcim.device_types.get(model=each_type['model']).delete()
                # 2c. If dev_type was not able to be created returns an error message
                except RequestError as e:
                    err_msg = ast.literal_eval(e.error)     # Converts string error message back into a list (literal_eval)
                    for err in err_msg:
                        if len(err) != 0:                   # safe guards against empty dicts returned in the error message
                            print("{} {}: {} - {}".format(u'\u274c', output_name, list(err.keys())[0], list(err.values())[0]))
        # 3. RETURN: Message returned (as long as no errors)
        if len(obj_exist_name) != 0:
            print('{}  {}: {} already exist'.format(u'\u26A0\uFE0F', output_name, str(obj_exist_name).replace('[', '').replace(']', '')))
        if len(all_result) != 0:                  # only triggered if results exist (try/except run)
            print("{} {}: '{}' successfully created".format(u'\u2705', output_name, str(all_result).replace('[', '').replace(']', '')))


############################ VLAN_VRF_CHECK: Due to depenencies on VL_GRP and VRF needs ia custom call ############################
    def vlan_vrf_check(self, output_name, api_attr, obj_fltr, obj_dm):
        # NEW_DMs: Creates 2 lists of DMs based on whether the object already exists or not
        obj_notexist_dm, obj_exist_name = ([] for i in range(2))
        for each_obj_dm in obj_dm:
            # 1a. CUSTOM VL_GRP/VRF: Checks whether the VLAN_GRP (creating VLANs) or VRF (creating PFXs) exists, if so gets the id of it.
            if operator.attrgetter(api_attr[1])(self.nb).get(name=each_obj_dm[obj_fltr[1]]['name']) != None:
                obj_id = operator.attrgetter(api_attr[1])(self.nb).get(name=each_obj_dm[obj_fltr[1]]['name']).id
                # 1b. Uses the ID to check whether the VLAN already exists in the VL_GRP or the the PFX already exists in the VRF
                if operator.attrgetter(api_attr[0])(self.nb).filter(**{obj_fltr[0]: each_obj_dm[obj_fltr[0]], obj_fltr[1] + '_id': obj_id}) == []:
                    obj_notexist_dm.append(each_obj_dm)
                # 1c. If the VLAN or PFX already exists adds the object name to already exist list
                else:
                    obj_exist_name.append(each_obj_dm[obj_fltr[0]])
            # 2. If VRF or VL_GRP dont exist prints message and doesnt add to list to create as cant create the VRF or VLAN without them
            elif operator.attrgetter(api_attr[1])(self.nb).get(name=each_obj_dm[obj_fltr[1]]['name']) == None:
                print("{} {}: {} - {} '{}' does not exist".format(u'\u274c', output_name, each_obj_dm[obj_fltr[0]], api_attr[1].split('.')[1][:-1],
                      each_obj_dm[obj_fltr[1]]['name']))

        # 3. PREFIX_VLAN: If the Prefix is associated to a VLAN checks against VL_GRP and role to get the unique ID (as can be duplicate vlans accross vl_grps)
        for each_obj_dm in reversed(obj_notexist_dm):
            #3a. FILTER: Matches any prefixes with a vlan assigned (VLANs or prefixes without a vlan wont have this dictionary)
            if each_obj_dm.get('vlan') != None:
                #3b. VL_GRP_NOT_EXIST: If the vlan-group doesnt exists removes the dict as it cant create the prefix
                if self.nb.ipam.vlan_groups.get(name=each_obj_dm['vl_grp']['name']) == None:
                    print("{} {}: {} - VLAN Group '{}' and/or VLAN '{}' do not exist".format(u'\u274c', output_name, each_obj_dm['prefix'],
                            each_obj_dm['vl_grp']['name'], each_obj_dm['vlan']))
                    obj_notexist_dm.remove(each_obj_dm)
                # 3c. VL_GRP_EXIST: If vl_grp exists gets the VLAN ID and add it to dict
                elif self.nb.ipam.vlan_groups.get(name=each_obj_dm['vl_grp']['name']) != None:
                    # Need to first get the slug as needed for group= filter in next 2 cmds
                    vl_grp_slug = self.nb.ipam.vlan_groups.get(name=each_obj_dm['vl_grp']['name'])['slug']
                    if self.nb.ipam.vlans.get(vid=each_obj_dm['vlan'], group=vl_grp_slug) != None:
                        each_obj_dm['vlan'] = dict(id=self.nb.ipam.vlans.get(vid=each_obj_dm['vlan'], group=vl_grp_slug).id)
                # 3d. VLAN_NOT_EXIST: If the vlan does not exists prints an error and removes the prefix
                else:
                    print("{} {}: {} - VLAN '{}' in VLAN Group '{}' does not exist".format(u'\u274c', output_name, each_obj_dm['prefix'], each_obj_dm['vlan'], each_obj_dm['vl_grp']['name']))
                    obj_notexist_dm.remove(each_obj_dm)
        self.obj_create(output_name, api_attr[0], obj_notexist_dm, obj_exist_name)


############################ 1. ORG_TNT_SITE_RACK: Creates the DM for organisation objects tenant, site, rack-group and rack ############################
    def create_org_tnt_site_rack(self):
        tnt, site, rack_grp, rack, rack_role = ([] for i in range(5))

        # 1a. TNT: If slug is empty replaces it with tenant name (lowercase) replacing whitespace with '_'
        for each_tnt in self.my_vars['tenant']:
            tnt.append(dict(name=each_tnt['name'], slug=each_tnt.get('slug', each_tnt['name'].replace(' ', '_').lower()), description=each_tnt.get('descr', ''),
                            tags=each_tnt.get('tags', [])))
            #1b. SITE: Uses temp dict and joins as the ASN cant be None, it must be an integrar. tenant is a nested dict as uses name rather than id
            for each_site in each_tnt.get('site', []):                  # Optional so uses 'get' with default empty list
                tnt_site_tag = list(set(each_tnt.get('tags', []) + each_site.get('tags', [])))
                temp_site = dict(name=each_site['name'], slug=each_site.get('slug', each_site['name'].replace(' ', '_').lower()), tenant=dict(name=each_tnt['name']),
                                 time_zone=each_site.get('time_zone', 'UTC'), description=each_site.get('descr', ''),
                                 physical_address=each_site.get('addr', ''), contact_name=each_site.get('contact', ''), contact_phone=each_site.get('phone', ''),
                                 contact_email=each_site.get('email', ''), tags=tnt_site_tag)
                if each_site.get('ASN') != None:
                    temp_site['asn'] = each_site['ASN']
                site.append(temp_site)
                #1c. RACK_GRP: List of rack groups at the site. Uses 'if' to stop errors for emtpy sites due to nested rack and rack groups
                if each_site.get('rack_grp') != None:
                    for each_rgrp in each_site['rack_grp']:
                        rack_grp.append(dict(name=each_rgrp['name'], slug=each_rgrp.get('slug', each_rgrp['name'].replace(' ', '_').lower()),
                                             site=dict(name=each_site['name']), description=each_rgrp.get('descr', '')))
                        #1d. RACK: List of racks within the rack group. Site and group are dict as using dictionary of attributes rather than ID
                        if each_rgrp.get('rack') != None:
                            for each_rack in each_rgrp['rack']:
                                temp_rack = (dict(name=each_rack['name'], site=dict(name=each_site['name']), group=dict(name=each_rgrp['name']),
                                                 tenant=dict(name=each_rack.get('tenant', each_tnt['name'])), u_height=each_rack.get('height', 42),
                                                 tags=list(set(tnt_site_tag + each_rack.get('tags', [])))))
                                if each_rack.get('role') != None:                    # Needed as Role cant be blank
                                    temp_rack['role'] = dict(name=each_rack['role'])
                                rack.append(temp_rack)
                        #1e. NESTED_RACK_GRP_RACK: List of nested rack groups and racks within them
                        if each_rgrp.get('rack_grp') != None:
                            for each_rgrp1 in each_rgrp['rack_grp']:
                                rack_grp.append(dict(name=each_rgrp1['name'], slug=each_rgrp1.get('slug', each_rgrp1['name'].replace(' ', '_').lower()),
                                                    site=dict(name=each_site['name']), description=each_rgrp1.get('descr', '')))
                                if each_rgrp1.get('rack') != None:
                                    for each_rack1 in each_rgrp1['rack']:
                                        temp_rack = dict(name=each_rack1['name'], site=dict(name=each_site['name']), group=dict(name=each_rgrp1['name']),
                                                        tenant=dict(name=each_rack1.get('tenant', each_tnt['name'])), u_height=each_rack1.get('height', 42),
                                                        role=dict(name=each_rack1['role']), tags=list(set(tnt_site_tag + each_rack1.get('tags', []))))
                                        if each_rack1.get('role') != None:              # Needed as Role cant be blank
                                            temp_rack['role'] = dict(name=each_rack1['role'])
                                        rack.append(temp_rack)
        # 1f. RR: Rack roles that can be used by a rack. If undefined sets the clour to white as cant be empty
        for each_rr in self.my_vars['rack_role']:
            rack_role.append(dict(name=each_rr['name'], slug=each_rr.get('slug', each_rr['name'].replace(' ', '_').lower()), description=each_rr.get('descr', ''),
                            color=each_rr.get('color', 'ffffff')))
        # 1g. The Data Models returned to the main method that are used to create the objects
        return dict(tnt=tnt, site=site, rack_grp=rack_grp, rack=rack, rack_role=rack_role)


############################ 2. DVC_MFTR_TYPE: Creates the DM for device objects manufacturer, platform, dvc_role and dvc_type ############################
    def create_dvc_type_role(self):
        dev_role, mftr, pltm, dev_type = ([] for i in range(4))
        # 2a. DVC_ROLE: List of device roles for all sites
        for each_role in self.my_vars['device_role']:
            dev_role.append(dict(name=each_role['name'], slug=each_role.get('slug', each_role['name'].replace(' ', '_').lower()),
                                 color=each_role.get('color', 'ffffff'), description=each_role.get('descr', ''), vm_role=each_role.get('vm_role', True)))
        # 2b. MFTR: List of manufacturers for all sites
        for each_mftr in self.my_vars['manufacturer']:
            mftr.append(dict(name=each_mftr['name'], slug=each_mftr.get('slug', each_mftr['name'].replace(' ', '_').lower()),
                             description=each_mftr.get('descr', '')))
            # 2c. PLATFORM: List of platforms for the manufacturer. Uses 'if' as platform is optional
            if each_mftr.get('platform') != None:
                for each_pltm in each_mftr['platform']:
                    pltm.append(dict(name=each_pltm['name'], slug=each_pltm.get('slug', each_pltm['name'].replace(' ', '_').lower()),
                                     manufacturer=dict(name=each_mftr['name']), description=each_pltm.get('descr', ''),
                                     napalm_driver=each_pltm.get('driver', each_pltm['name'].replace(' ', '_').lower())))
            # 2d. DVC_TYPE: List of device types for the manufacturer. Uses 'if' as device_type is optional
            if each_mftr.get('device_type') != None:
                for each_type in each_mftr['device_type']:
                    intf, con, pwr, f_port, r_port = ([] for i in range(5))         # Lists need to be emptied each loop (dev_type)
                    with open(os.path.join(dvc_type_dir, each_type), 'r') as file_content:
                        dev_type_tmpl = yaml.load(file_content, Loader=yaml.FullLoader)
                    # Create lists of interfaces, consoles, power, front_ports and rear_ports
                    for each_intf in dev_type_tmpl.get('interfaces', []):
                        intf.append(dict(device_type=dict(model=dev_type_tmpl['model']), name=each_intf['name'], type=each_intf['type'],
                                         mgmt_only=each_intf.get('mgmt_only', False)))
                    for each_con in dev_type_tmpl.get('console-ports', []):
                        con.append(dict(device_type=dict(model=dev_type_tmpl['model']), name=each_con['name'], type=each_con['type']))
                    for each_pwr in dev_type_tmpl.get('power-ports', []):
                        pwr.append(dict(device_type=dict(model=dev_type_tmpl['model']), name=each_pwr['name'], type=each_pwr['type']))
                    for each_fport in dev_type_tmpl.get('front_port', []):
                        # Creates the list of front and rear ports from a start and end port number (of front port)
                        for each_port in range(each_fport['start_port'], each_fport['end_port'] + 1):
                            r_port.append(dict(device_type=dict(model=dev_type_tmpl['model']), name=each_port, type=each_fport['type']))
                            f_port.append(dict(device_type=dict(model=dev_type_tmpl['model']), name=each_port, type=each_fport['type']))
                    # Create list of device types which also includes the interfaces, consoles, power, front_port and rear_port lists
                    dev_type.append(dict(manufacturer=dict(name=each_mftr['name']), model=dev_type_tmpl['model'], slug=dev_type_tmpl['slug'],
                                         part_number=dev_type_tmpl['part_number'], u_height=dev_type_tmpl.get('u_height', 1),
                                         is_full_depth=dev_type_tmpl.get('is_full_depth', True), interface=intf, console=con, power=pwr,
                                         front_port=f_port, rear_port=r_port))
        # 2e. The Data Models returned to the main method that are used to create the objects
        return dict(dev_role=dev_role, mftr=mftr, pltm=pltm, dev_type=dev_type)


############################ 3. IPAM_VRF_VLAN: Creates the DM for IPAM objects RIR, aggregate, VRF and VLAN ############################
    def create_ipam(self):
        rir, aggr, role, vlan_grp, vlan, vrf, prefix = ([] for i in range(7))
        # 3a. RIR: If slug is empty replaces it with tenant name (lowercase) replacing whitespace with '_'
        for each_rir in self.my_vars['rir']:
            rir.append(dict(name=each_rir['name'], slug=each_rir.get('slug', each_rir['name'].replace(' ', '_').lower()),
                            description=each_rir.get('descr', ''), is_private=each_rir.get('is_private', False)))
            # 3b. AGGR: Create ranges that are associated to the RIR
            if each_rir.get('ranges') != None:
                for each_aggr in each_rir['ranges']:
                    aggr.append(dict(rir=dict(name=each_rir['name']), prefix=each_aggr['prefix'], description=each_aggr.get('descr', ''),
                                     tags=each_aggr.get('tags', [])))

        for each_role in self.my_vars['role']:
            # 3c. ROLE: Provides segregation of networks (i.e prod, npe, etc), applies to all VLANs and prefixes beneath it
            role.append(dict(name=each_role['name'], slug=each_role.get('slug', each_role['name'].replace(' ', '_').lower()), description=each_role.get('descr', '')))
            for each_site in each_role['site']:
                # Gets the tenant name from site, leaves it blank if API call fails
                try:
                    tenant = dict(self.nb.dcim.sites.get(name=each_site['name']))['tenant']['name']
                except:
                    tenant = None
                #3d. VL_GRP_EXIST: If vlan Group is defined creates VLAN_GRP & VLAN
                if each_site.get('vlan_grp') != None:
                    # VL_GRP holds VLANs that are unique to that group.
                    for each_vlgrp in each_site['vlan_grp']:
                        vl_tenant = each_vlgrp.get('tenant', tenant)           # Replaces site tenant if set under vl_grp
                        vl_tags = each_site.get('tags', []) + each_vlgrp.get('tags', [])    # Joins any parent tags
                        vlan_grp.append(dict(name=each_vlgrp['name'], slug=each_vlgrp.get('slug', each_vlgrp['name'].replace(' ', '_').lower()),
                                             site=dict(name=each_site['name']), description=each_vlgrp.get('descr', '')))
                        # VLANs are associated to the vl_grp, tenant, site and role. The VL_GRP and role keep them unique
                        for each_vl in each_vlgrp['vlan']:
                            vlan.append(dict(vid=each_vl['id'], name=each_vl['name'], site=dict(name=each_site['name']), role=dict(name=each_role['name']),
                                            tenant=dict(name=each_vl.get('tenant', vl_tenant)), group=dict(name=each_vlgrp['name']),description=each_vl.get('descr', ''),
                                            tags=list(set(vl_tags + each_vl.get('tags', [])))))
                        #3e. VRF_&_PFX: If the VRF is defined creates VRF and Prefixes. Prefixes are linked to the VLANs (SVIs) within the VLAN group
                        if each_vlgrp.get('vrf') != None:
                            for each_vrf in each_vlgrp['vrf']:
                                vrf_tenant = each_vrf.get('tenant', tenant)           # Replaces site tenant if set under vrf
                                vrf_tags = list(set(each_site.get('tags', []) + each_vrf.get('tags', [])))   # Joins any parent tags
                                tmp_vrf = dict(name=each_vrf['name'], description=each_vrf.get('descr', ''), enforce_unique=each_vrf.get('unique', True),
                                               tenant=dict(name=vrf_tenant), tags=vrf_tags)
                                if each_vrf.get('rd') != None:
                                    tmp_vrf['rd'] = each_vrf['rd']
                                vrf.append(tmp_vrf)
                                # PREFIX: Associated to a VRF, role and possibly a VLAN. VRF and role are what make the prefix unique
                                for each_pfx in each_vrf['prefix']:
                                    pfx_tags = list(set(vrf_tags + each_pfx.get('tags', [])))   # Joins any parent tags
                                    tmp_pfx = (dict(prefix=each_pfx['pfx'], role=dict(name=each_role['name']), is_pool=each_pfx.get('pool', True),
                                                    vrf=dict(name=each_vrf['name']), vl_grp=dict(name=each_vlgrp['name']), description=each_pfx.get('descr', ''),
                                                    site=dict(name=each_site['name']), tenant=dict(name=each_pfx.get('tenant', vrf_tenant)), tags=pfx_tags))
                                    if each_pfx.get('vl') != None:
                                        tmp_pfx['vlan'] = each_pfx['vl']
                                    prefix.append(tmp_pfx)
                #3f. VRF_WITH_NO_VLANs: If Prefixes do not have VLANs no VL_GRP, the VRF is the main dictionary with PFX dictionaries underneath it
                if each_site.get('vrf') != None:
                    # VRF: Creates VRF withs its optional settings
                    for each_vrf in each_site['vrf']:
                        vrf_tenant = each_vrf.get('tenant', tenant)           # Replaces site tenant if set under vrf
                        vrf_tags = list(set(each_site.get('tags', []) + each_vrf.get('tags', [])))   # Joins any parent tags
                        tmp_vrf = dict(name=each_vrf['name'], description=each_vrf.get('descr', ''), enforce_unique=each_vrf.get('unique', True),
                                       tenant=dict(name=vrf_tenant), tags=vrf_tags)
                        if each_vrf.get('rd') != None:
                            tmp_vrf['rd'] = each_vrf['rd']
                        vrf.append(tmp_vrf)
                        # PREFIX: Associated to a VRF and role, has no VLANs associated. VRF and role are what make the prefix unique
                        for each_pfx in each_vrf['prefix']:
                            pfx_tags = list(set(vrf_tags + each_pfx.get('tags', [])))   # Joins any parent tags
                            tmp_pfx = (dict(prefix=each_pfx['pfx'], role=dict(name=each_role['name']), is_pool=each_pfx.get('pool', True), vrf=dict(name=each_vrf['name']),
                                            description=each_pfx.get('descr', ''), site=dict(name=each_site['name']), tenant=dict(name=each_pfx.get('tenant', vrf_tenant)),
                                            tags=pfx_tags))
                            prefix.append(tmp_pfx)
        # 3g. The Data Models returned to the main method that are used to create the objects
        return dict(rir=rir, aggr=aggr, role=role, vlan_grp=vlan_grp, vlan=vlan, vrf=vrf, prefix=prefix)


############################ 4. CRT_PVDR: Creates the DM for Circuit, Provider and Circuit Type ############################
    def create_crt(self):
        crt_type, pvdr, crt = ([] for i in range(3))
        # 4a. CIRCUIT_TYPE: A classification of circuits
        for each_type in self.my_vars['circuit_type']:
            crt_type.append(dict(name=each_type['name'], slug=each_type.get('slug', each_type['name'].replace(' ', '_').lower()), description=each_type.get('descr', '')))
        # 4b. PROVIDER: Containers that hold cicuits by the same provider of connectivity (ISP)
        for each_pvdr in self.my_vars['provider']:
            tmp_pvdr = dict(name=each_pvdr['name'], slug=each_pvdr.get('slug', each_pvdr['name'].replace(' ', '_').lower()), account=each_pvdr.get('account_num', ''),
                            portal_url=each_pvdr.get('portal_url', ''), noc_contact=each_pvdr.get('noc_contact', ''), admin_contact=each_pvdr.get('admin_contact', ''),
                            comments=each_pvdr.get('comments', ''), tags=each_pvdr.get('tags', []))
            # Optional setting ASN
            if each_pvdr.get('asn') != None:
                tmp_pvdr['asn'] = each_pvdr['asn']
            pvdr.append(tmp_pvdr)
            # 4b. CIRCUIT: Each circuit belongs to a provider and must be assigned a circuit ID which is unique to that provider
            for each_crt in each_pvdr['circuit']:
                tmp_crt = dict(cid=each_crt['cid'], type=dict(name=each_crt['type']), provider=dict(name=each_pvdr['name']), description=each_crt.get('descr', ''),
                               tags=list(set(each_pvdr.get('tags', []) + each_crt.get('tags', []))))
                # Optional settings Tenant and commit_rate need to be only added if set as empty vlaues breal API calls
                if each_crt.get('tenant') != None:
                    tmp_crt['tenant'] = dict(name=each_crt['tenant'])
                if each_crt.get('commit_rate') != None:
                    tmp_crt['commit_rate'] = each_crt['commit_rate']
                crt.append(tmp_crt)
        # 4c. The Data Models returned to the main method that are used to create the objects
        return dict(crt_type=crt_type, pvdr=pvdr, crt=crt)


############################ 5. VIRTUAL: Creates the DM for Cluster, cluster type and cluster group ############################
    def create_vrtl(self):
        cltr_type, cltr, cltr_grp = ([] for i in range(3))

         # 5a. CLUSTER_GROUP: Optional, can be used to group clusters such as by region. Only required if used in clusters
        if self.my_vars['cluster_group'] != None:
            for each_grp in self.my_vars['cluster_group']:
                cltr_grp.append(dict(name=each_grp['name'], slug=each_grp.get('slug', each_grp['name'].replace(' ', '_').lower()), description=each_grp.get('descr', '')))
        # 5b. CLUSTER_TYPE: Represents a technology or mechanism by which to group clusters
        for each_type in self.my_vars['cluster_type']:
            cltr_type.append(dict(name=each_type['name'], slug=each_type.get('slug', each_type['name'].replace(' ', '_').lower()), description=each_type.get('descr', '')))
            # 5c. CLUSTERS: Holds VMs and physical resources which hosts VMs
            if each_type.get('cluster') != None:
                # If defined sets default values that can be used for all clusters
                grp = each_type.get('group', None)
                tags = each_type.get('tags', [])
                site = each_type.get('site', None)
                if each_type.get('tenant') != None:
                    tenant = each_type['tenant']
                # If tenant is undefined gets the tenant name from the site, leaves it blank if API call fails
                elif each_type.get('tenant') == None:
                    try:
                        tenant = dict(self.nb.dcim.sites.get(name=site))['tenant']['name']
                    except:
                        tenant = None
                # Builds each cluster DM
                for each_cltr in each_type['cluster']:
                    cltr_tags = list(set(tags + each_cltr.get('tags', [])))
                    tmp_cltr = (dict(name=each_cltr['name'], type=dict(name=each_type['name']), comments=each_cltr.get('comment', ''), tags=cltr_tags))
                    # Optional settings tenant, site or group cant be blank in API call so only adds dict if is defined
                    tmp_grp = each_type.get('group', grp)
                    if each_cltr.get('tenant', tenant) != None:
                        tmp_cltr['tenant'] = dict(name=each_cltr.get('tenant', tenant))
                    if each_cltr.get('site', site) != None:
                        tmp_cltr['site'] = dict(name=each_cltr.get('site', site))
                    if tmp_grp != None:
                        tmp_cltr['group'] = dict(name=tmp_grp)
                    cltr.append(tmp_cltr)
         # 5d. The Data Models returned to the main method that are used to create the objects
        return dict(cltr_type=cltr_type, cltr=cltr, cltr_grp=cltr_grp)


######################## ENGINE: Runs the methods of the script ########################
def main():
    # Opens netbox connection and loads the variable file
    script, first = argv
    nbox = Nbox()
    # 1. ORG_TNT_SITE_RACK: Create all the organisation objects
    org = nbox.create_org_tnt_site_rack()
    # Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
    nbox.obj_check('Rack Role', 'dcim.rack_roles', 'name', org['rack_role'])
    nbox.obj_check('Tenant', 'tenancy.tenants', 'name', org['tnt'])
    nbox.obj_check('Site', 'dcim.sites', 'name', org['site'])
    nbox.obj_check('Rack-group', 'dcim.rack_groups', 'name', org['rack_grp'])
    nbox.obj_check('Rack', 'dcim.racks', 'name', org['rack'])

    # 2. DVC_MTFR_TYPE: Create all the objects required to create devices
    dvc = nbox.create_dvc_type_role()
    # Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
    nbox.obj_check('Device-role', 'dcim.device_roles', 'name', dvc['dev_role'])
    nbox.obj_check('Manufacturer', 'dcim.manufacturers', 'name', dvc['mftr'])
    nbox.obj_check('Platform', 'dcim.platforms', 'name', dvc['pltm'])
    nbox.obj_check('Device-type', 'dcim.device_types', 'model', dvc['dev_type'])

    # 3. IPAM_VRF_VLAN: Create all the IPAM objects
    ipam = nbox.create_ipam()
    # Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
    nbox.obj_check('RIRs', 'ipam.rirs', 'name', ipam['rir'])
    nbox.obj_check('Aggregates', 'ipam.aggregates', 'prefix', ipam['aggr'])
    nbox.obj_check('Prefix/VLAN Role', 'ipam.roles', 'name', ipam['role'])
    nbox.obj_check('VLAN Group', 'ipam.vlan-groups', 'name', ipam['vlan_grp'])
    nbox.obj_check('VRF', 'ipam.vrfs', 'name', ipam['vrf'])
    # First check if VL/PFX exist in VL_GRP/VRF, then if exist in ROLE.
    nbox.vlan_vrf_check('VLAN', ['ipam.vlans', 'ipam.vlan_groups'], ['name', 'group'], ipam['vlan'])
    nbox.vlan_vrf_check('Prefix', ['ipam.prefixes', 'ipam.vrfs'], ['prefix', 'vrf'], ipam['prefix'])

    # 4. CRT_PVDR: Create all the Circuit objects
    crt = nbox.create_crt()
    # Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
    nbox.obj_check('Circuit Type', 'circuits.circuit-types', 'name', crt['crt_type'])
    nbox.obj_check('Provider', 'circuits.providers', 'name', crt['pvdr'])
    nbox.obj_check('Circuit', 'circuits.circuits', 'cid', crt['crt'])

    # 5. VIRTUAL: Creates all the Cluster objects
    vrtl = nbox.create_vrtl()
    # Passed into nbox_call are: Friendly name (for user message), path of api call, filter (to check if object already exists), DM of data
    nbox.obj_check('Cluster Type', 'virtualization.cluster-types', 'name', vrtl['cltr_type'])
    nbox.obj_check('Cluster Group', 'virtualization.cluster-groups', 'name', vrtl['cltr_grp'])
    nbox.obj_check('Cluster', 'virtualization.clusters', 'name', vrtl['cltr'])

if __name__ == '__main__':
    main()