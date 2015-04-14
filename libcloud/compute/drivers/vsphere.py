# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
VMware vSphere driver. Uses pyvmomi - https://github.com/vmware/pyvmomi
Code inspired by https://github.com/vmware/pyvmomi-community-samples

Author: Markos Gogoulos -  mgogoulos@mist.io
"""

try:
    from pyVim import connect
    from pyVmomi import vmodl
except ImportError:
    raise ImportError('Missing "pyvmomi" dependency. You can install it '
                      'using pip - pip install pyvmomi')

import atexit

from libcloud.common.types import InvalidCredsError
from libcloud.compute.base import NodeDriver
from libcloud.compute.base import NodeLocation
from libcloud.compute.base import NodeImage
from libcloud.compute.base import Node
from libcloud.compute.types import NodeState, Provider
from libcloud.utils.networking import is_public_subnet



class VSphereNodeDriver(NodeDriver):
    name = 'VMware vSphere'
    website = 'http://www.vmware.com/products/vsphere/'
    type = Provider.VSPHERE

    NODE_STATE_MAP = {
        'poweredOn': NodeState.RUNNING,
        'poweredOff': NodeState.STOPPED,
        'suspended': NodeState.SUSPENDED,
    }

    def __init__(self, host, username, password):
        """Initialize a connection by providing a hostname,
        username and password
        """

        try:
            self.connection = connect.SmartConnect(host=host, user=username,
                                                   pwd=password)
            atexit.register(connect.Disconnect, self.connection)

        except Exception as exc:
            if 'incorrect user name' in getattr(exc, 'msg', ''):
                raise InvalidCredsError('Check your username and password are valid')
            message = str(exc.message)
            if 'Connection refused' in message or 'is not a VIM server' in message:
                raise Exception('Check that the host provided is a vSphere installation')
            if 'Name or service not known' in message:
                raise Exception('Check that the vSphere host is accessible')

    def list_locations(self):
        """
        Lists locations
        """
        return []

    def list_sizes(self):
        """
        Lists sizes
        """
        return []

    def list_images(self):
        """
        Lists images
        """
        return []

    def list_nodes(self):
        """
        Lists nodes
        """
        nodes = []
        content = self.connection.RetrieveContent()
        children = content.rootFolder.childEntity
        for child in children:
            if hasattr(child, 'vmFolder'):
                datacenter = child
            else:
            # some other non-datacenter type object
                continue
            vm_folder = datacenter.vmFolder
            vm_list = vm_folder.childEntity

            for virtual_machine in vm_list:
                node = self._to_node(virtual_machine, 10)
                if node:
                    nodes.append(node)
        return nodes

    def _to_node(self, virtual_machine, depth=1):
        maxdepth = 10
        # if this is a group it will have children. if it does, recurse into them
        # and then return
        if hasattr(virtual_machine, 'childEntity'):
            if depth > maxdepth:
                return
            vmList = virtual_machine.childEntity
            for c in vmList:
                self._to_node(c, depth + 1)
            return

        summary = virtual_machine.summary

        name = summary.config.name
        path = summary.config.vmPathName
        memory = summary.config.memorySizeMB
        cpus = summary.config.numCpu
        operating_system = summary.config.guestFullName
        # mist.io needs this metadata
        os_type = 'unix'
        if 'Microsoft' in str(operating_system):
            os_type = 'windows'
        uuid = summary.config.instanceUuid
        annotation = summary.config.annotation
        state = summary.runtime.powerState
        status = self.NODE_STATE_MAP.get(state, NodeState.UNKNOWN)
        boot_time = summary.runtime.bootTime

        if summary.guest is not None:
            ip_address = summary.guest.ipAddress

        overallStatus = summary.overallStatus
        public_ips = []
        private_ips = []

        extra = {
            "path": path,
            "operating_system": operating_system,
            "os_type": os_type,
            "memory": memory,
            "cpus": cpus,
            "overallStatus": overallStatus
        }

        if boot_time:
            extra['boot_time'] = boot_time.isoformat()
        if annotation:
            extra['annotation'] = annotation

        if ip_address:
            if is_public_subnet(ip_address):
                public_ips.append(ip_address)
            else:
                private_ips.append(ip_address)

        node = Node(id=uuid, name=name, state=status,
                    public_ips=public_ips, private_ips=private_ips,
                    driver=self, extra=extra)
        node._uuid = uuid
        return node

    def reboot_node(self, node):
        """FIXME: implement
        """
        pass

    def destroy_node(self, node):
        """FIXME: implement
        """
        pass

    def ex_stop_node(self, node):
        """FIXME: implement
        """
        pass

    def ex_start_node(self, node):
        """FIXME: implement
        """
        pass
