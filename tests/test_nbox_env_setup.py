import pytest
import yaml
import pynetbox
from pynetbox.core.query import RequestError
import operator

import os

# # Directory that holds inventory files
test_dir = os.path.dirname(__file__)
# test_inventory = os.path.join(test_dir, "test_inventory")
test_input = os.path.join(test_dir, "test_files", "test_inputs.yml")
from nbox_env_setup import Nbox
from nbox_env_setup import Organisation
from nbox_env_setup import Devices
from nbox_env_setup import Ipam
from nbox_env_setup import Circuits
from nbox_env_setup import Virtualisation
import tests.test_files.device_types as device_types


# For docker test environment
token = "0123456789abcdef0123456789abcdef01234567"
netbox_url = "http://10.10.10.104:8000"


# # ----------------------------------------------------------------------------
# # Fixture to initialise Nornir and load inventory
# # ----------------------------------------------------------------------------
# Load variable file used by all the tests
@pytest.fixture(scope="session", autouse=True)
def load_vars():
    global my_vars
    with open(test_input, "r") as file_content:
        my_vars = yaml.load(file_content, Loader=yaml.FullLoader)


# Test API calls to netbox
@pytest.fixture(scope="class")
def load_nbox():
    global nbox
    nbox = Nbox(netbox_url, token)
    yield nbox
    # Delete nbox test objects that where created
    nb = pynetbox.api(url=netbox_url, token=token)
    del_nbox_obj(nb, "tenancy.tenants", "name", my_vars["tenant"][0]["name"])
    del_nbox_obj(nb, "extras.tags", "name", "UTEST_tag")


# Delete unittest netbox objects
def del_nbox_obj(nb, api_attr, obj_fltr, obj_name):
    fltr = {obj_fltr: obj_name}
    try:
        if operator.attrgetter(api_attr)(nb).get(**fltr) != None:
            obj = operator.attrgetter(api_attr)(nb).get(**fltr)
            obj.delete()
    except RequestError as e:
        print(
            "❌ An error was raised deleting netbox unit test '{api_attr}' object '{obj_name}', check if it exists and delete manually"
        )


# Load the vars for Organisation class
@pytest.fixture(scope="class")
def organisation_vars():
    global org, tnt1, tnt2, site1, site2, loc, rack, rr
    org = Organisation(my_vars["tenant"], my_vars["rack_role"])
    tnt1 = my_vars["tenant"][0]
    tnt2 = my_vars["tenant"][1]
    site1 = my_vars["tenant"][0]["site"][0]
    site2 = my_vars["tenant"][1]["site"][0]
    loc = my_vars["tenant"][0]["site"][0]["location"][0]
    rack = my_vars["tenant"][0]["site"][0]["location"][0]["rack"][0]
    rr = my_vars["rack_role"][0]


# Load the vars for Devices class
@pytest.fixture(scope="class")
def devices_vars():
    global dvc, dev_role, mftr, pltm, dev_type_swi, dev_type_pp
    dvc = Devices(my_vars["device_role"], my_vars["manufacturer"])
    dev_role = my_vars["device_role"][0]
    mftr = my_vars["manufacturer"][0]
    pltm = my_vars["manufacturer"][0]["platform"][0]
    dev_type_swi = my_vars["manufacturer"][0]["device_type"][0]
    dev_type_pp = my_vars["manufacturer"][0]["device_type"][1]


# Load the vars for IPAM class
@pytest.fixture(scope="class")
def ipam_vars():
    global ipam, rir, aggr, role, vlan_grp, vlan, vrf, pfx
    ipam = Ipam(my_vars["rir"], my_vars["role"])
    rir = my_vars["rir"][0]
    aggr = my_vars["rir"][0]["ranges"][0]
    role = my_vars["role"][0]
    vlan_grp = my_vars["role"][0]["site"][0]["vlan_grp"][0]
    vlan = my_vars["role"][0]["site"][0]["vlan_grp"][0]["vlan"][0]
    vrf = my_vars["role"][0]["site"][0]["vlan_grp"][0]["vrf"][0]
    vlan = my_vars["role"][0]["site"][0]["vlan_grp"][0]["vrf"][0]["prefix"][0]


# Load the vars for Circuits class
@pytest.fixture(scope="class")
def circuits_vars():
    global crt, crt_type, pvdr, cirt
    crt = Circuits(my_vars["circuit_type"], my_vars["provider"])
    crt_type = my_vars["circuit_type"][0]
    pvdr = my_vars["provider"][0]
    cirt = my_vars["provider"][0]["circuit"][0]


# Load the vars for Virtualisation class
@pytest.fixture(scope="class")
def virtualisation_vars():
    global vrtl, cltr_grp, cltr_type, cltr1, cltr2
    vrtl = Virtualisation(my_vars["cluster_group"], my_vars["cluster_type"])
    cltr_grp = my_vars["cluster_group"][0]
    cltr_type = my_vars["cluster_type"][0]
    cltr1 = my_vars["cluster_type"][0]["cluster"][0]
    cltr2 = my_vars["cluster_type"][0]["cluster"][1]


# ----------------------------------------------------------------------------
# 1.NBOX_API: Testing of API calls to netbox
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("load_nbox")
class TestNbox:

    # Test object creation failure error reporting works
    def test_obj_create_err(self, capsys):
        err_msg = "❌ obj_create: Netbox object creation error reporting failed"
        desired_result = "❌ Tenant 'slug' - This field is required.\n"
        try:
            nbox.obj_create(
                "Tenant",
                "tenancy.tenants",
                [{"name": my_vars["tenant"][0]["name"]}],
                [],
            )
        except SystemExit:
            pass
        assert capsys.readouterr().out == desired_result, err_msg

    # Test object creation works
    def test_obj_create(self, capsys):
        err_msg = "❌ obj_create: Netbox object creation failed"
        cr_tnt = [
            {
                "description": my_vars["tenant"][0]["descr"],
                "name": my_vars["tenant"][0]["name"],
                "slug": "utest_tnt",
                "tags": [],
            }
        ]
        desired_result = "✅ Tenant: 'UTEST_tenant' successfully created\n"
        try:
            nbox.obj_create("Tenant", "tenancy.tenants", cr_tnt, [])
        except SystemExit:
            pass
        assert capsys.readouterr().out == desired_result, err_msg

    # Test object lookup
    def test_obj_check(self):
        err_msg = "❌ obj_check: Checking for existence of netbox object failed"
        desired_result = {
            "notexist_dm": [{"name": "no_tenant"}],
            "exist_name": ["UTEST_tenant"],
        }
        actual_result = nbox.obj_check(
            "tenancy.tenants",
            "name",
            [{"name": my_vars["tenant"][0]["name"]}, {"name": "no_tenant"}],
        )
        assert actual_result == desired_result, err_msg

    # Test creating tag or getting existing tag ID
    def test_get_or_create_tag(self):
        err_msg = "❌ get_or_create_tag: Creation of tag or checking for existence of tag failed"
        actual_result = nbox.get_or_create_tag({"UTEST_tag": "c0c0c0"})
        assert isinstance(actual_result[0], int), err_msg
        # Run twice as first create, then second time make sure can get the ID
        assert isinstance(actual_result[0], int), err_msg

    # Test creating slug from object name
    def test_make_slug(self):
        err_msg = "❌ make_slug: Creation of slug from object name failed"
        desired_result = "utest_test_slug"
        actual_result = nbox.make_slug("UTEST TEST SLUG")
        assert actual_result == desired_result, err_msg


# ----------------------------------------------------------------------------
# 4. ORG: Testing of organisartion data-models
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("organisation_vars")
class TestOrganisation:

    # 1a. TNT: Test method for creating dict to add a tenant
    def test_cr_tnt(self):
        err_msg = "❌ cr_tnt: Creation of tenant dictionary failed"
        global desired_tnt1
        desired_tnt1 = {
            "description": tnt1["descr"],
            "name": tnt1["name"],
            "slug": "utest_tnt1",
            "tags": [],
        }
        actual_result = org.cr_tnt(tnt1)
        assert actual_result == desired_tnt1, err_msg

    # 1b. SITE: Test method for creating dict to add a site
    def test_cr_site(self):
        err_msg = "❌ cr_site: Creation of site dictionary failed"
        global desired_site1
        desired_site1 = {
            "asn": site1["ASN"],
            "contact_email": site1["email"],
            "contact_name": site1["contact"],
            "contact_phone": site1["phone"],
            "description": site1["descr"],
            "name": site1["name"],
            "physical_address": site1["addr"],
            "slug": "utest_site1",
            "tags": [],
            "tenant": {"name": tnt1["name"]},
            "time_zone": site1["time_zone"],
        }
        actual_result = org.cr_site(tnt1, site1)
        assert actual_result == desired_site1, err_msg

    # 1c. LOC_RACK: Test method for creating dict to add a location and rack
    def test_cr_loc_rack(self):
        err_msg = "❌ cr_loc_rack: Creation of {} dictionary failed"
        global desired_loc, desired_rack, desired_ch_loc

        desired_loc = {
            "description": loc["descr"],
            "name": loc["name"],
            "site": {"name": site1["name"]},
            "slug": "utest_location",
        }
        desired_rack = [
            {
                "location": {"name": loc["name"]},
                "name": rack["name"],
                "role": {"name": rr["name"]},
                "site": {"name": site1["name"]},
                "tags": [],
                "tenant": {"name": tnt2["name"]},
                "u_height": rack["height"],
            }
        ]
        actual_result = org.cr_loc_rack(loc, site1, tnt1, None)
        assert actual_result[0] == desired_loc, err_msg.format("parent location")
        assert actual_result[1] == desired_rack, err_msg.format("rack")
        desired_ch_loc = {
            "description": loc["location"][0]["descr"],
            "name": loc["location"][0]["name"],
            "site": {"name": site1["name"]},
            "slug": "utest_child_location",
            "parent": {"name": loc["name"]},
        }
        actual_result = org.cr_loc_rack(loc["location"][0], site1, tnt1, loc["name"])
        assert actual_result[0] == desired_ch_loc, err_msg.format("child location")

    # 1d. RACK-ROLE: Test method for creating dict to add a rack-role
    def test_cr_rr(self):
        err_msg = "❌ cr_rr: Creation of location and rack-role dictionary failed"
        global desired_rr
        desired_rr = {
            "color": rr["color"],
            "description": rr["descr"],
            "name": rr["name"],
            "slug": "utest_rack_role",
        }
        actual_result = org.cr_rr(rr)
        assert actual_result == desired_rr, err_msg

    # 1e. ORG: Test method for creating dict to add all organisation objects
    def test_create_tnt_site_rack(self):
        err_msg = (
            "❌ create_tnt_site_rack: Creation of organisation objects dictionary failed"
        )
        # breakpoint()
        # Need to initialise a fresh or keeps location/rack from test_cr_loc_rack
        org = Organisation(my_vars["tenant"], my_vars["rack_role"])

        desired_site = [desired_site1]
        desired_site2 = {
            "contact_email": "",
            "contact_name": "",
            "contact_phone": "",
            "description": "",
            "name": site2["name"],
            "physical_address": "",
            "slug": "utest_site2",
            "tags": [],
            "tenant": {"name": tnt2["name"]},
            "time_zone": "UTC",
        }
        desired_site.append(desired_site2)

        desired_tnt = [desired_tnt1]
        desired_tnt2 = {
            "description": "",
            "name": tnt2["name"],
            "slug": "utest_tenant2",
            "tags": [],
        }
        desired_tnt.append(desired_tnt2)

        actual_result = org.create_tnt_site_rack()
        desired_result = dict(
            tnt=desired_tnt,
            site=desired_site,
            location=[desired_loc],
            child_loc=[desired_ch_loc],
            rack=desired_rack,
            rack_role=[desired_rr],
        )
        assert actual_result == desired_result, err_msg


# ----------------------------------------------------------------------------
# 2. DVC_TYPE: Testing of device-types data-models
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("devices_vars")
class TestDevices:

    # 2a. DVC_ROLE: Test method for creating dict to add a device role
    def test_cr_dev_role(self):
        err_msg = "❌ cr_dev_role: Creation of Device Role dictionary failed"
        global desired_dev_role
        desired_dev_role = {
            "color": dev_role["color"],
            "description": dev_role["descr"],
            "name": dev_role["name"],
            "slug": dev_role["slug"],
            "vm_role": dev_role["vm_role"],
        }
        actual_result = dvc.cr_dev_role(dev_role)
        assert actual_result == desired_dev_role, err_msg

    # 2b. MFTR: Test method for creating dict to add a manufacturer
    def test_cr_mftr(self):
        err_msg = "❌ cr_mftr: Creation of Manufacturer dictionary failed"
        global desired_mftr
        desired_mftr = {
            "description": mftr["descr"],
            "name": mftr["name"],
            "slug": mftr["slug"],
        }
        actual_result = dvc.cr_mftr(mftr)
        assert actual_result == desired_mftr, err_msg

    # 2c. PLTM: Test method for creating dict to add a platform
    def test_cr_pltm(self):
        err_msg = "❌ cr_pltm: Creation of Platform dictionary failed"
        global desired_pltm
        desired_pltm = {
            "description": "",
            "manufacturer": {"name": mftr["name"]},
            "name": pltm["name"],
            "napalm_driver": pltm["driver"],
            "slug": pltm["slug"],
        }
        actual_result = dvc.cr_pltm(mftr["name"], pltm)
        assert actual_result == desired_pltm, err_msg

    # 2d. CONN: Test method for creating dict to add a connection
    def test_cr_conn(self):
        err_msg = "❌ cr_conn: Creation of Device Type Connection dictionary failed"
        global desired_conn
        desired_conn = {
            "device_type": {"model": "Catalyst 3560-CX-12PC-S"},
            "name": "GigabitEthernet1/0/1",
            "type": "1000base-t",
        }
        actual_result = dvc.cr_conn(
            "Catalyst 3560-CX-12PC-S", "GigabitEthernet1/0/1", "1000base-t"
        )
        assert actual_result == desired_conn, err_msg

    # 2e. DEV_TYPE_SWI: Test method for creating dict to add a switch device_type
    def test_cr_dev_type_sw(self):
        err_msg = "❌ cr_dev_type: Creation of Switch Device Type dictionary failed"
        global desired_dev_type_sw
        desired_dev_type_sw = device_types.sw
        actual_result = dvc.cr_dev_type(mftr["name"], dev_type_swi)
        assert actual_result == desired_dev_type_sw, err_msg

        # 2f. DEV_TYPE_PP: Test method for creating dict to add a patch panel device_type

    def test_cr_dev_type_pp(self):
        err_msg = "❌ cr_dev_type: Creation of Patch Panel Device Type dictionary failed"
        global desired_dev_type_pp
        desired_dev_type_pp = device_types.pp
        actual_result = dvc.cr_dev_type(mftr["name"], dev_type_pp)
        assert actual_result == desired_dev_type_pp, err_msg

    # 2g. DVC: Test method for creating dict to add all Device Type objects
    def test_create_dvc_type_role(self):
        err_msg = "❌ create_create_dvc_type_role: Creation of Device Types objects dictionary failed"
        desired_dev_type = [desired_dev_type_sw]
        desired_dev_type.append(desired_dev_type_pp)
        actual_result = dvc.create_dvc_type_role()
        desired_result = dict(
            dev_role=[desired_dev_role],
            mftr=[desired_mftr],
            pltm=[desired_pltm],
            dev_type=desired_dev_type,
        )
        assert actual_result == desired_result, err_msg


# ----------------------------------------------------------------------------
# 3. IPAM: Testing of IPAM data-models
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("ipam_vars")
class TestIpam:

    # 3a. RIR: Test method for creating dict to add a RIR
    def test_cr_rir(self):
        err_msg = "❌ cr_rir: Creation of RIR dictionary failed"
        global desired_rir
        desired_rir = {
            "description": rir["descr"],
            "is_private": rir["is_private"],
            "name": rir["name"],
            "slug": "rfc1918",
        }
        actual_result = ipam.cr_rir(rir)
        assert actual_result == desired_rir, err_msg

    # 3b. AGGR: Test method for creating dict to add a RIR aggregate
    def test_cr_aggr(self):
        err_msg = "❌ cr_aggr: Creation of RIR Aggregate dictionary failed"
        global desired_aggr
        desired_aggr = {}
        actual_result = ipam.cr_aggr(rir, aggr)
        assert actual_result == desired_aggr, err_msg

    # # 3c. ROLE: Test method for creating dict to add a VRF/VLAN Role
    # def test_cr_role(self):
    #     err_msg = "❌ cr_role: Creation of VRF/VLAN Role dictionary failed"
    #     global desired_role
    #     desired_role = {}
    #     actual_result = ipam.cr_role(rir, role)
    #     assert actual_result == desired_role, err_msg

    # # 3d. VL+GRP: Test method for creating dict to add a VLAN Group
    # def test_cr_vl_grp(self):
    #     err_msg = "❌ cr_vl_grp: Creation of VLAN Group dictionary failed"
    #     global desired_vl_grp
    #     desired_vl_grp = {}
    #     actual_result = ipam.cr_role(role["site"][0]["name"], vlan_grp)
    #     assert actual_result == desired_vl_grp, err_msg

    # # 3e. VLAN: Test method for creating dict to add a VLAN
    # def test_cr_vlan(self):
    #     err_msg = "❌ cr_vlan: Creation of VLAN Group dictionary failed"
    #     global desired_vlan
    #     desired_vlan = {}
    #     # NEED TENTANT, guess depneds on inheritnace
    #     actual_result = ipam.cr_role(role["name"], "NEED_TNT", vlan_grp, vlan)
    #     assert actual_result == desired_vlan, err_msg

    # # 3h. VRF: Test method for creating dict to add a VRF (no VLAN association)
    # def test_cr_vrf(self):
    #     err_msg = "❌ cr_vrf Creation of VRF dictionary (no VLAN association) failed"
    #     global desired_vrf
    #     desired_vrf = {}
    #     # NEED TENTANT, guess depneds on inheritnace
    #     actual_result = ipam.cr_vrf("NEED_TNT", vrf)
    #     assert actual_result == desired_vlan, err_msg

    # # 3i. VRF_VLAN: Test method for creating dict to add a VRF within VLAN Group
    # def test_cr_pfx(self):
    #     err_msg = "❌ cr_vrf Creation of VRF dictionary (within VLAN Group) failed"
    #     global desired_pfx
    #     desired_pfx = {}
    #     # NEED TENTANT, guess depneds on inheritnace
    #     actual_result = ipam.cr_pfx(role["name"], role["site"][0]["name"], "NEED_TNT", vlan_grp["name"], vrf["name"], pfx)
    #     assert actual_result == desired_pfx, err_msg

    # # 3j. IPAM: Test method for creating dict to add all IPAM objects
    # def test_create_ipam(self):
    #     err_msg = "❌ create_ipam: Creation of IPAM objects dictionary failed"

    #     actual_result = ipam.create_ipam()
    #     desired_result = dict(
    #         rir=[desired_rir],
    #         aggr=[desired_aggr],
    #         role=[desired_role],
    #         vlan_grp=[desired_vl_grp],
    #         vlan=[desired_vlan],
    #         vrf=[desired_vrf],
    #         prefix=[desired_pfx],
    #     )
    #     assert actual_result == desired_result, err_msg


# ----------------------------------------------------------------------------
# 4. CRT: Testing of circuits data-models
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("circuits_vars")
class TestCircuits:

    # 4a. CRT_TYPE: Test method for creating dict to add a circuit type
    def test_cr_crt_type(self):
        err_msg = "❌ cr_cir_type: Creation of Circuit Type dictionary failed"
        global desired_crt_type
        desired_crt_type = {
            "description": crt_type["descr"],
            "name": crt_type["name"],
            "slug": crt_type["slug"],
        }
        actual_result = crt.cr_crt_type(crt_type)
        assert actual_result == desired_crt_type, err_msg

    # 4b. PROVIDER: Test method for creating dict to add a provider
    def test_cr_pvdr(self):
        err_msg = "❌ cr_pvdr: Creation of Provider dictionary failed"
        global desired_pvdr
        desired_pvdr = {
            "account": pvdr["account_num"],
            "admin_contact": pvdr["admin_contact"],
            "asn": pvdr["asn"],
            "comments": pvdr["comments"],
            "name": pvdr["name"],
            "noc_contact": pvdr["noc_contact"],
            "portal_url": pvdr["portal_url"],
            "slug": pvdr["slug"],
            "tags": [],
        }
        actual_result = crt.cr_pvdr(pvdr)
        assert actual_result == desired_pvdr, err_msg

    # 4c. CIRCUIT: Test method for creating dict to add a circuit
    def test_cr_crt(self):
        err_msg = "❌ cr_crt: Creation of Circuit Type dictionary failed"
        global desired_crt
        desired_crt = {
            "cid": str(cirt["cid"]),
            "commit_rate": cirt["commit_rate"],
            "description": cirt["descr"],
            "provider": {"name": pvdr["name"]},
            "tags": [],
            "tenant": {"name": cirt["tenant"]},
            "type": {"name": cirt["type"]},
        }
        actual_result = crt.cr_crt(pvdr, cirt)
        assert actual_result == desired_crt, err_msg

    # 1e. CRT: Test method for creating dict to add all circuits objects
    def test_create_crt_pvdr(self):
        err_msg = "❌ create_crt_pvdr: Creation of circuit objects dictionary failed"
        actual_result = crt.create_crt_pvdr()
        desired_result = dict(
            crt_type=[desired_crt_type],
            pvdr=[desired_pvdr],
            crt=[desired_crt],
        )
        assert actual_result == desired_result, err_msg


# ----------------------------------------------------------------------------
# 5. VRTL: Testing of virtualisation data-models
# ----------------------------------------------------------------------------
@pytest.mark.usefixtures("virtualisation_vars")
class TestVirtualisation:

    # 5a. CLTR_GRP: Test method for creating dict to add a cluster group
    def test_cr_cltr_grp(self):
        err_msg = "❌ cr_cltr_grp: Creation of cluster group dictionary failed"
        global desired_cltr_grp
        desired_cltr_grp = {
            "name": cltr_grp["name"],
            "slug": "utest_cluster_grp",
            "description": cltr_grp["descr"],
        }
        actual_result = vrtl.cr_cltr_grp(cltr_grp)
        assert actual_result == desired_cltr_grp, err_msg

    # 5b. CLTR_TYPE: Test method for creating dict to add a cluster type
    def test_cr_cltr_type(self):
        err_msg = "❌ cr_cltr_type: Creation of cluster type dictionary failed"
        global desired_cltr_type
        desired_cltr_type = {
            "description": "",
            "name": cltr_type["name"],
            "slug": "utest_cltr_type",
        }
        actual_result = vrtl.cr_cltr_type(cltr_type)
        assert actual_result == desired_cltr_type, err_msg

    # 5c. CLTR: Test method for creating dict to add a cluster
    def test_cr_cltr(self):
        err_msg = "❌ cr_cltr: Creation of cluster dictionary failed"
        global desired_cltr1
        desired_cltr1 = {
            "comments": cltr1["comment"],
            "group": {"name": cltr_type["group"]},
            "name": cltr1["name"],
            "site": {"name": cltr_type["site"]},
            "tenant": {"name": cltr_type["tenant"]},
            "type": {"name": cltr_type["name"]},
        }
        actual_result = vrtl.cr_cltr(cltr_type, cltr1)
        assert actual_result == desired_cltr1, err_msg

    # 5d. CLTR: Test method for creating dict to add a cluster with inherited tenant and site
    def test_cr_cltr_inherited(self):
        err_msg = (
            "❌ cr_cltr: Creation of cluster with inherited objects dictionary failed"
        )
        global desired_cltr2
        desired_cltr2 = {
            "comments": "",
            "group": {"name": cltr2["group"]},
            "name": cltr2["name"],
            "site": {"name": cltr2["site"]},
            "tenant": {"name": cltr2["tenant"]},
            "type": {"name": cltr_type["name"]},
        }
        actual_result = vrtl.cr_cltr(cltr_type, cltr2)
        assert actual_result == desired_cltr2, err_msg

    # 5e. VRTL: Test method for creating dict to add all virtualisation objects
    def test_create_vrtl(self):
        err_msg = "❌ create_vrtl: Creation of virtualisation objects dictionary failed"
        actual_result = vrtl.create_vrtl()
        desired_cltr = [desired_cltr1]
        desired_cltr.append(desired_cltr2)
        print(desired_cltr)
        desired_result = dict(
            cltr_type=[desired_cltr_type],
            cltr_grp=[desired_cltr_grp],
            cltr=desired_cltr,
        )
        assert actual_result == desired_result, err_msg
