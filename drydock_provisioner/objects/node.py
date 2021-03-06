# Copyright 2017 AT&T Intellectual Property.  All other rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Models for drydock_provisioner
#
"""Drydock model of a baremetal node."""

from defusedxml.ElementTree import fromstring
import logging
from oslo_versionedobjects import fields as ovo_fields

import drydock_provisioner.error as errors
import drydock_provisioner.config as config
import drydock_provisioner.objects as objects
import drydock_provisioner.objects.hostprofile
import drydock_provisioner.objects.base as base
import drydock_provisioner.objects.fields as hd_fields


@base.DrydockObjectRegistry.register
class BaremetalNode(drydock_provisioner.objects.hostprofile.HostProfile):

    VERSION = '1.0'

    fields = {
        'addressing': ovo_fields.ObjectField('IpAddressAssignmentList'),
        'boot_mac': ovo_fields.StringField(nullable=True),
    }

    # A BaremetalNode is really nothing more than a physical
    # instantiation of a HostProfile, so they both represent
    # the same set of CIs
    def __init__(self, **kwargs):
        super(BaremetalNode, self).__init__(**kwargs)
        self.logicalnames = {}
        self.logger = logging.getLogger(
            config.config_mgr.conf.logging.global_logger_name)

    # Compile the applied version of this model sourcing referenced
    # data from the passed site design
    def compile_applied_model(self, site_design, state_manager):
        self.logger.debug("Applying host profile to node %s" % self.name)
        self.apply_host_profile(site_design)
        self.logger.debug("Applying hardware profile to node %s" % self.name)
        self.apply_hardware_profile(site_design)
        self.source = hd_fields.ModelSource.Compiled
        self.logger.debug("Resolving kernel parameters on node %s" % self.name)
        self.resolve_kernel_params(site_design)
        self.logger.debug("Resolving device aliases on node %s" % self.name)
        self.apply_logicalnames(site_design, state_manager)
        return

    def apply_host_profile(self, site_design):
        self.apply_inheritance(site_design)
        return

    # Translate device aliases to physical selectors and copy
    # other hardware attributes into this object
    def apply_hardware_profile(self, site_design):
        if self.hardware_profile is None:
            raise ValueError("Hardware profile not set")

        hw_profile = site_design.get_hardware_profile(self.hardware_profile)

        for i in getattr(self, 'interfaces', []):
            for s in i.get_hw_slaves():
                selector = hw_profile.resolve_alias("pci", s)
                if selector is None:
                    selector = objects.HardwareDeviceSelector()
                    selector.selector_type = 'name'
                    selector.address = s

                i.add_selector(selector)

        for p in getattr(self, 'partitions', []):
            selector = hw_profile.resolve_alias("scsi", p.get_device())
            if selector is None:
                selector = objects.HardwareDeviceSelector()
                selector.selector_type = 'name'
                selector.address = p.get_device()
            p.set_selector(selector)

        return

    def resolve_kernel_params(self, site_design):
        """Check if any kernel parameter values are supported references."""
        if not self.hardware_profile:
            raise ValueError("Hardware profile not set.")

        hwprof = site_design.get_hardware_profile(self.hardware_profile)

        if not hwprof:
            raise ValueError("Hardware profile not found.")

        resolved_params = dict()
        for p, v in self.kernel_params.items():
            try:
                rv = self.get_kernel_param_value(v, hwprof)
                resolved_params[p] = rv
            except (errors.InvalidParameterReference, errors.CpuSetNotFound,
                    errors.HugepageConfNotFound) as ex:
                resolved_params[p] = v
                msg = ("Error resolving parameter reference on node %s: %s" %
                       (self.name, str(ex)))
                self.logger.warning(msg)

        self.kernel_params = resolved_params

    def get_kernel_param_value(self, value, hwprof):
        """If ``value`` is a reference, resolve it otherwise return ``value``

        Support some referential values to extract data from the HardwareProfile

        hardwareprofile:cpuset.<setname>
        hardwareprofile:hugepages.<confname>.size
        hardwareprofile:hugepages.<confname>.count

        If ``value`` matches none of the above forms, just return the value as passed.

        :param value: the value string as specified in the node definition
        :param hwprof: the assigned HardwareProfile for this node
        """
        if value.startswith('hardwareprofile:'):
            (_, ref) = value.split(':', 1)
            if ref:
                (ref_type, ref_val) = ref.split('.', 1)
                if ref_type == 'cpuset':
                    return hwprof.get_cpu_set(ref_val)
                elif ref_type == 'hugepages':
                    (conf, field) = ref_val.split('.', 1)
                    hp_conf = hwprof.get_hugepage_conf(conf)
                    if field in ['size', 'count']:
                        return getattr(hp_conf, field)
                    else:
                        raise errors.InvalidParameterReference(
                            "Invalid field %s specified." % field)
                else:
                    raise errors.InvalidParameterReference(
                        "Invalid configuration %s specified." % ref_type)
            else:
                return value

        else:
            return value

    def get_applied_interface(self, iface_name):
        for i in getattr(self, 'interfaces', []):
            if i.get_name() == iface_name:
                return i

        return None

    def get_network_address(self, network_name):
        for a in getattr(self, 'addressing', []):
            if a.network == network_name:
                return a.address

        return None

    def find_fs_block_device(self, fs_mount=None):
        if not fs_mount:
            return (None, None)

        if self.volume_groups is not None:
            for vg in self.volume_groups:
                if vg.logical_volumes is not None:
                    for lv in vg.logical_volumes:
                        if lv.mountpoint is not None and lv.mountpoint == fs_mount:
                            return (vg, lv)
        if self.storage_devices is not None:
            for sd in self.storage_devices:
                if sd.partitions is not None:
                    for p in sd.partitions:
                        if p.mountpoint is not None and p.mountpoint == fs_mount:
                            return (sd, p)
        return (None, None)

    def _apply_logicalname(self, xml_root, alias_name, bus_type, address):
        """Given xml_data, checks for a matching businfo and returns the logicalname

        :param xml_root: Parsed ElementTree, it is searched for the logicalname.
        :param alias_name: String value of the current device alias, it is returned
                           if a logicalname is not found.
        :param bus_type: String value that is used to find the logicalname.
        :param address: String value that is used to find the logicalname.
        :return: String value of the logicalname or the alias_name if logicalname is not found.
        """
        nodes = xml_root.findall(
            ".//node[businfo='" + bus_type + "@" + address + "'].logicalname")
        if len(nodes) >= 1 and nodes[0].text:
            if (len(nodes) > 1):
                self.logger.info("Multiple nodes found for businfo=%s@%s" %
                                 (bus_type, address))
            for logicalname in reversed(nodes[0].text.split("/")):
                self.logger.debug(
                    "Logicalname build dict: alias_name = %s, bus_type = %s, address = %s, "
                    "to logicalname = %s" % (alias_name, bus_type, address,
                                             logicalname))
                return logicalname
        self.logger.debug(
            "Logicalname build dict: alias_name = %s, bus_type = %s, address = %s, not found"
            % (alias_name, bus_type, address))
        return alias_name

    def apply_logicalnames(self, site_design, state_manager):
        """Gets the logicalnames for devices from lshw.

        :param site_design: SiteDesign object.
        :param state_manager: DrydockState object.
        :return: Returns sets a dictionary of aliases that map to logicalnames in self.logicalnames.
        """
        logicalnames = {}

        results = state_manager.get_build_data(
            node_name=self.get_name(), latest=True)
        xml_data = None
        for result in results:
            if result.generator == "lshw":
                xml_data = result.data_element
                break

        if xml_data:
            xml_root = fromstring(xml_data)
            for hardware_profile in site_design.hardware_profiles:
                for device in hardware_profile.devices:
                    logicalname = self._apply_logicalname(
                        xml_root, device.alias, device.bus_type,
                        device.address)
                    logicalnames[device.alias] = logicalname
        else:
            self.logger.info("No Build Data found for node_name %s" %
                             (self.get_name()))

        self.logicalnames = logicalnames

    def get_logicalname(self, alias):
        """Gets the logicalname from self.logicalnames for an alias or returns the alias if not in the dictionary.
        """
        if (self.logicalnames and self.logicalnames.get(alias)):
            self.logger.debug("Logicalname input = %s with output %s." %
                              (alias, self.logicalnames[alias]))
            return self.logicalnames[alias]
        else:
            self.logger.debug(
                "Logicalname input = %s not in logicalnames dictionary." %
                alias)
            return alias


@base.DrydockObjectRegistry.register
class BaremetalNodeList(base.DrydockObjectListBase, base.DrydockObject):

    VERSION = '1.0'

    fields = {'objects': ovo_fields.ListOfObjectsField('BaremetalNode')}


@base.DrydockObjectRegistry.register
class IpAddressAssignment(base.DrydockObject):

    VERSION = '1.0'

    fields = {
        'type': ovo_fields.StringField(),
        'address': ovo_fields.StringField(nullable=True),
        'network': ovo_fields.StringField(),
    }

    def __init__(self, **kwargs):
        super(IpAddressAssignment, self).__init__(**kwargs)

    # IpAddressAssignment keyed by network
    def get_id(self):
        return self.network


@base.DrydockObjectRegistry.register
class IpAddressAssignmentList(base.DrydockObjectListBase, base.DrydockObject):

    VERSION = '1.0'

    fields = {'objects': ovo_fields.ListOfObjectsField('IpAddressAssignment')}
