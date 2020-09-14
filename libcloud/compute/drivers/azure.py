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
"""Azure Compute driver

"""
import httplib
import re
import time
import collections
import random
import sys
import copy
import base64
import os
import binascii
import multiprocessing.pool
import requests

from libcloud.utils.py3 import urlquote as url_quote
from libcloud.utils.py3 import urlunquote as url_unquote
from libcloud.utils.py3 import ET
from libcloud.common.azure import AzureServiceManagementConnection
from libcloud.compute.providers import Provider, get_driver
from libcloud.compute.base import Node, NodeDriver, NodeLocation, NodeSize
from libcloud.compute.base import NodeImage, StorageVolume
from libcloud.compute.base import KeyPair
from libcloud.compute.types import NodeState
from libcloud.common.types import LibcloudError
from libcloud.pricing import get_size_price

from datetime import datetime
from xml.dom import minidom
from xml.sax.saxutils import escape as xml_escape
from httplib import (HTTPSConnection)
from libcloud.compute.drivers.azure_arm import locations_mapping
from libcloud.common.types import InvalidCredsError

if sys.version_info < (3,):
    _unicode_type = unicode  # NOQA  pylint: disable=undefined-variable

    def _str(value):
        if isinstance(value, unicode):  # NOQA  pylint: disable=undefined-variable
            return value.encode('utf-8')

        return str(value)
else:
    _str = str
    _unicode_type = str

__version__ = '1.0.0'


azure_service_management_host = 'management.core.windows.net'
_USER_AGENT_STRING = 'libcloudazurecompute/' + __version__
X_MS_VERSION = '2013-08-01'

"""
Sizes must be hardcoded because Microsoft doesn't provide an API to fetch them.
From http://msdn.microsoft.com/en-us/library/windowsazure/dn197896.aspx
"""

AZURE_COMPUTE_INSTANCE_TYPES = [
    {
        'id': 'ExtraSmall',
        'name': 'ExtraSmall (1 cores, 768 MB)',
        'ram': 768,
        'disk': 20,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': '1'
    },
    {
        'id': 'Small',
        'name': 'Small (1 cores, 1792 MB)',
        'ram': 1792,
        'disk': 70,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 1
    },
    {
        'id': 'Medium',
        'name': 'Medium (2 cores, 3584 MB)',
        'ram': 3584,
        'disk': 135,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 2
    },
    {
        'id': 'Large',
        'name': 'Large Instance',
        'ram': 7168,
        'disk': 285,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 4
    },
    {
        'id': 'ExtraLarge',
        'name': 'ExtraLarge (8 cores, 14336 MB)',
        'ram': 14336,
        'disk': 605,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 8
    },
    {
        'id': 'A5',
        'name': 'A5 (2 cores, 14336 MB)',
        'ram': 14336,
        'disk': 135,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 2
    },
    {
        'id': 'A6',
        'name': 'A6 (4 cores, 28672 MB)',
        'ram': 28672,
        'disk': 285,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 4
    },
    {
        'id': 'A7',
        'name': 'A7 (8 cores, 57344 MB)',
        'ram': 57344,
        'disk': 605,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 8
    },
    {
        'id': 'A8',
        'name': 'A8 (8 cores, 57344 MB)',
        'ram': 57344,
        'disk': 382,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 8
    },
    {
        'id': 'A9',
        'name': 'A9 (16 cores, 114688 MB)',
        'ram': 114688,
        'disk': 382,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 16
    },
    {
        'id': 'A10',
        'name': 'A10 (8 cores, 56000 MB)',
        'ram': 56000,
        'disk': 382,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 8
    },
    {
        'id': 'A11',
        'name': 'A11 (16 cores, 112000 MB)',
        'ram': 112000,
        'disk': 382,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 16
    },
    {
        'id': 'Basic_A0',
        'name': 'Basic_A0 (1 cores, 768 MB)',
        'ram': 768,
        'disk': 20.00,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 1
    },
    {
        'id': 'Basic_A1',
        'name': 'Basic_A1 (1 cores, 1792 MB)',
        'ram': 1792,
        'disk': 40.00,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 1
    },
    {
        'id': 'Basic_A2',
        'name': 'Basic_A2 (2 cores, 3584 MB)',
        'ram': 3584,
        'disk': 60.00,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 2
    },
    {
        'id': 'Basic_A3',
        'name': 'Basic_A3 (4 cores, 7168 MB)',
        'ram': 7168,
        'disk': 120.00,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 4
    },
    {
        'id': 'Basic_A4',
        'name': 'Basic_A4 (8 cores, 14336 MB)',
        'ram': 14336,
        'disk': 240.00,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 8
    },
    {
        'id': 'Standard_D1',
        'name': 'Standard_D1 (1 cores, 3584 MB)',
        'ram': 3584,
        'disk': 127,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 1
    },
    {
        'id': 'Standard_D2',
        'name': 'Standard_D2 (2 cores, 7168 MB)',
        'ram': 7168,
        'disk': 102,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 2
    },
    {
        'id': 'Standard_D3',
        'name': 'Standard_D3 (4 cores, 14336 MB)',
        'ram': 14336,
        'disk': 256,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 4
    },
    {
        'id': 'Standard_D4',
        'name': 'Standard_D4 (8 cores, 28672 MB)',
        'ram': 28672,
        'disk': 512,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 8
    },
    {
        'id': 'Standard_D11',
        'name': 'Standard_D11 (2 cores, 14336 MB)',
        'ram': 14336,
        'disk': 100,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 2
    },
    {
        'id': 'Standard_D12',
        'name': 'Standard_D12 (4 cores, 28672 MB)',
        'ram': 28672,
        'disk': 200,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 4
    },
    {
        'id': 'Standard_D13',
        'name': 'Standard_D13 (8 cores, 57344 MB)',
        'ram': 57344,
        'disk': 400,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 8
    },
    {
        'id': 'Standard_D14',
        'name': 'Standard_D14 (16 cores, 114688 MB)',
        'ram': 114688,
        'disk': 800,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 16
    },


    {
        'id': 'Standard_D1_v2',
        'name': 'Standard_D1_v2 (1 cores, 3584 MB)',
        'ram': 3584,
        'disk': 50,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 1
    },
    {
        'id': 'Standard_D2_v2',
        'name': 'Standard_D2_v2 (2 cores, 7168 MB)',
        'ram': 7168,
        'disk': 102,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 2
    },
    {
        'id': 'Standard_D3_v2',
        'name': 'Standard_D3_v2 (4 cores, 14336 MB)',
        'ram': 14336,
        'disk': 256,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 4
    },
    {
        'id': 'Standard_D4_v2',
        'name': 'Standard_D4_v2 (8 cores, 28672 MB)',
        'ram': 28672,
        'disk': 512,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 8
    },
    {
        'id': 'Standard_D5_v2',
        'name': 'Standard_D5_v2 (16 cores, 57344 MB)',
        'ram': 57344,
        'disk': 100,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 16
    },

    {
        'id': 'Standard_D11_v2',
        'name': 'Standard_D11_v2 (2 cores, 14336 MB)',
        'ram': 14336,
        'disk': 100,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 2
    },
    {
        'id': 'Standard_D12_v2',
        'name': 'Standard_D12_v2 (4 cores, 28672 MB)',
        'ram': 28672,
        'disk': 200,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 4
    },
    {
        'id': 'Standard_D13_v2',
        'name': 'Standard_D13_v2 (8 cores, 57344 MB)',
        'ram': 57344,
        'disk': 400,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 8
    },
    {
        'id': 'Standard_D14_v2',
        'name': 'Standard_D14_v2 (16 cores, 114688 MB)',
        'ram': 114688,
        'disk': 800,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 16
    },
    {
        'id': 'Standard_D15_v2',
        'name': 'Standard_D15_v2 (20 cores, 140000 MB)',
        'ram': 114688,
        'disk': 1000,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 20
    },
    {
        'id': 'F1',
        'name': 'F1 (1 core, 2000 MB)',
        'ram': 2000,
        'disk': 16,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 1
    },
    {
        'id': 'F2',
        'name': 'F2 (2 cores, 4000 MB)',
        'ram': 4000,
        'disk': 32,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 2
    },
    {
        'id': 'F4',
        'name': 'F4 (4 cores, 8000 MB)',
        'ram': 8000,
        'disk': 64,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 4
    },
    {
        'id': 'F8',
        'name': 'F8 (8 cores, 16000 MB)',
        'ram': 16000,
        'disk': 128,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 8
    },
    {
        'id': 'F16',
        'name': 'F16 (16 cores, 32000 MB)',
        'ram': 32000,
        'disk': 256,
        'bandwidth': None,
        'max_data_disks': None,
        'cores': 16
    },
]

_KNOWN_SERIALIZATION_XFORMS = {
    'include_apis': 'IncludeAPIs',
    'message_id': 'MessageId',
    'content_md5': 'Content-MD5',
    'last_modified': 'Last-Modified',
    'cache_control': 'Cache-Control',
    'account_admin_live_email_id': 'AccountAdminLiveEmailId',
    'service_admin_live_email_id': 'ServiceAdminLiveEmailId',
    'subscription_id': 'SubscriptionID',
    'fqdn': 'FQDN',
    'private_id': 'PrivateID',
    'os_virtual_hard_disk': 'OSVirtualHardDisk',
    'logical_disk_size_in_gb': 'LogicalDiskSizeInGB',
    'logical_size_in_gb': 'LogicalSizeInGB',
    'os': 'OS',
    'persistent_vm_downtime_info': 'PersistentVMDowntimeInfo',
    'copy_id': 'CopyId',
}


class AzureNodeDriver(NodeDriver):
    connectionCls = AzureServiceManagementConnection
    name = "Azure Node Provider"
    website = 'http://windowsazure.com'
    type = Provider.AZURE

    _instance_types = AZURE_COMPUTE_INSTANCE_TYPES
    _blob_url = ".blob.core.windows.net"
    features = {'create_node': ['password', 'ssh_key']}
    service_location = collections.namedtuple(
        'service_location', ['is_affinity_group', 'service_location'])

    NODE_STATE_MAP = {
        'RoleStateUnknown': NodeState.UNKNOWN,
        'CreatingVM': NodeState.PENDING,
        'StartingVM': NodeState.PENDING,
        'CreatingRole': NodeState.PENDING,
        'StartingRole': NodeState.PENDING,
        'ReadyRole': NodeState.RUNNING,
        'BusyRole': NodeState.PENDING,
        'StoppingRole': NodeState.PENDING,
        'StoppingVM': NodeState.PENDING,
        'DeletingVM': NodeState.PENDING,
        'StoppedVM': NodeState.STOPPED,
        'RestartingRole': NodeState.REBOOTING,
        'CyclingRole': NodeState.TERMINATED,
        'FailedStartingRole': NodeState.STOPPED,
        'FailedStartingVM': NodeState.STOPPED,
        'UnresponsiveRole': NodeState.STOPPED,
        'StoppedDeallocated': NodeState.STOPPED,
    }

    def __init__(self, subscription_id=None, key_file=None, **kwargs):
        """
        subscription_id contains the Azure subscription id in the form of GUID
        key_file contains the Azure X509 certificate in .pem form
        """
        self.subscription_id = subscription_id
        self.key_file = key_file
        super(AzureNodeDriver, self).__init__(self.subscription_id, self.key_file,
                                              secure=True, **kwargs)

    def ex_list_cloud_services(self):
        """
        List cloud services

        """
        data = self._perform_get(
            '/' + self.subscription_id + '/services/hostedservices', HostedServices)

        services = [i.service_name for i in data]
        return services

    def list_sizes(self):
        """
        Lists all sizes

        :rtype: ``list`` of :class:`NodeSize`
        """
        # TODO: grub data from
        # https://management.core.windows.net/subscription_id/hostedservices

        sizes = [self._to_node_size(value) for value in self._instance_types]

        return sizes

    def list_images(self, location=None):
        """
        Lists all images

        :rtype: ``list`` of :class:`NodeImage`
        """
        data = self._perform_get(self._get_image_path(), Images)

        images = [self._to_image(i) for i in data]

        if location != None:
            images = [
                image for image in images if location in image.extra["location"]]

        return images

    def list_locations(self):
        """
        Lists all locations

        :rtype: ``list`` of :class:`NodeLocation`
        """
        data = self._perform_get(
            '/' + self.subscription_id + '/locations', Locations)

        return [self._to_location(l) for l in data]

    def list_nodes(self, ex_cloud_service_name=None):
        """
        List nodes for a cloud service, or for all cloud services
        If ex_cloud_service_name specified, list nodes for this cloud
        service, otherwise show all nodes

        :param      ex_cloud_service_name: Cloud Service name
        :type       ex_cloud_service_name: ``str``

        :rtype: ``list`` of :class:`Node`
        """

        if ex_cloud_service_name:
            return self.list_nodes_for_cloud_service(ex_cloud_service_name=ex_cloud_service_name)
        else:
            #first get a list of services
            #then get VMs for each service
            #use multiprocessing to query services on parallel
            #since libcloud driver instance is not thread safe, the easiest solution is
            #to create a new driver instance inside each thread.
            #http://ci.apache.org/projects/libcloud/docs/other/using-libcloud-in-multithreaded-and-async-environments.html
            services = self.ex_list_cloud_services()
            def _list_one(service):
                driver = get_driver(self.type)(self.key, self.secret)
                try:
                    return driver.list_nodes_for_cloud_service(service)
                except:
                    return []
            pool = multiprocessing.pool.ThreadPool(8)
            results = pool.map(_list_one, services)
            pool.terminate()
            machines = []
            for result in results:
                machines.extend(result)

        return machines


    def list_nodes_for_cloud_service(self, ex_cloud_service_name):
        """
        List nodes for cloud service

        ex_cloud_service_name parameter is used to scope the request
        to a specific Cloud Service. This is a required parameter as
        nodes cannot exist outside of a Cloud Service nor be shared
        between a Cloud Service within Azure.

        :param      ex_cloud_service_name: Cloud Service name
        :type       ex_cloud_service_name: ``str``

        :rtype: ``list`` of :class:`Node`
        """

        response = self._perform_get(
            self._get_hosted_service_path(ex_cloud_service_name) +
            '?embed-detail=True',
            None)
        # if response.status != 200 :
        #    raise LibcloudError('Message: %s, Body: %s, Status code: %d' %
        #                        (response.error, response.body, response.status)
        #                        , driver=self)

        data = self._parse_response(response, HostedService)

        try:
            nodes = [self._to_node(n) for n in
                    data.deployments[0].role_instance_list]

            for node in nodes:
                node.extra['cloud_service_name'] = ex_cloud_service_name
                node.extra['location'] = data.hosted_service_properties.location
            return nodes
        except IndexError:
            return []

    def reboot_node(self, node=None, ex_cloud_service_name=None,
                    ex_deployment_slot=None):
        """
        Reboots a node.

        ex_cloud_service_name parameter is used to scope the request
        to a specific Cloud Service. This is a required parameter as
        nodes cannot exist outside of a Cloud Service nor be shared
        between a Cloud Service within Azure.

        :param      ex_cloud_service_name: Cloud Service name
        :type       ex_cloud_service_name: ``str``

        :param      ex_deployment_name: Options are "production" (default)
                                         or "Staging". (Optional)
        :type       ex_deployment_name: ``str``

        :rtype: ``bool``
        """

        if not ex_cloud_service_name:
            raise ValueError("ex_cloud_service_name is required.")

        if not ex_deployment_slot:
            ex_deployment_slot = "production"

        if not node:
            raise ValueError("node is required.")

        _deployment_name = self._get_deployment(
            service_name=ex_cloud_service_name,
            deployment_slot=ex_deployment_slot).name

        try:
            response = self._perform_post(
                self._get_deployment_path_using_name(
                    ex_cloud_service_name, _deployment_name) + '/roleinstances/'
                + _str(node.id) + '?comp=reboot', '')

            if response.status != 202:
                raise LibcloudError('Message: %s, Body: %s, Status code: %d' %
                                    (response.error, response.body,
                                     response.status), driver=self)

            if self._parse_response_for_async_op(response):
                return True
            else:
                return False
        except Exception:
            return False

    def ex_start_node(self, node=None, ex_cloud_service_name=None,
                    ex_deployment_slot=None):
        """
        Starts a node
        """
        if not ex_cloud_service_name:
            raise ValueError("ex_cloud_service_name is required.")

        if not ex_deployment_slot:
            ex_deployment_slot = "production"

        if not node:
            raise ValueError("node is required.")

        _deployment_name = self._get_deployment(
            service_name=ex_cloud_service_name,
            deployment_slot=ex_deployment_slot).name

        start_txt = '<StartRoleOperation xmlns="http://schemas.microsoft.com/windowsazure" xmlns:i="http://www.w3.org/2001/XMLSchema-instance"><OperationType>StartRoleOperation</OperationType></StartRoleOperation>'

        try:
            response = self._perform_post(
                self._get_deployment_path_using_name(
                    ex_cloud_service_name, _deployment_name) + '/roleinstances/'
                + _str(node.id) + '/Operations', start_txt)

            if response.status != 202:
                raise LibcloudError('Message: %s, Body: %s, Status code: %d' %
                                    (response.error, response.body,
                                     response.status), driver=self)

            if self._parse_response_for_async_op(response):
                return True
            else:
                return False
        except Exception, e:
            return False

    def ex_stop_node(self, node=None, ex_cloud_service_name=None,
                    ex_deployment_slot=None):
        """
        Stops a node
        """
        if not ex_cloud_service_name:
            raise ValueError("ex_cloud_service_name is required.")

        if not ex_deployment_slot:
            ex_deployment_slot = "production"

        if not node:
            raise ValueError("node is required.")

        _deployment_name = self._get_deployment(
            service_name=ex_cloud_service_name,
            deployment_slot=ex_deployment_slot).name

        shutdown_txt = '<ShutdownRoleOperation xmlns="http://schemas.microsoft.com/windowsazure" xmlns:i="http://www.w3.org/2001/XMLSchema-instance"><OperationType>ShutdownRoleOperation</OperationType><PostShutdownAction>Stopped</PostShutdownAction></ShutdownRoleOperation>'

        try:
            response = self._perform_post(
                self._get_deployment_path_using_name(
                    ex_cloud_service_name, _deployment_name) + '/roleinstances/'
                + _str(node.id) + '/Operations', shutdown_txt)

            if response.status != 202:
                raise LibcloudError('Message: %s, Body: %s, Status code: %d' %
                                    (response.error, response.body,
                                     response.status), driver=self)

            if self._parse_response_for_async_op(response):
                return True
            else:
                return False
        except Exception, e:
            return False

    def list_volumes(self, node=None):
        """
        Lists volumes of the disks in the image repository that are
        associated with the specificed subscription.

        Pass Node object to scope the list of volumes to a single
        instance.

        :rtype: ``list`` of :class:`StorageVolume`
        """

        data = self._perform_get(self._get_disk_path(), Disks)

        volumes = [self._to_volume(volume=v, node=node) for v in data]

        return volumes

    def create_node(self, name, size, image, location, ex_cloud_service_name=None, endpoint_ports=[], custom_data=None,
                    **kwargs):
        """Create Azure Virtual Machine

           Reference: http://bit.ly/1fIsCb7
           [www.windowsazure.com/en-us/documentation/]

           We default to:

           + 3389/TCP - RDP - 1st Microsoft instance.
           + RANDOM/TCP - RDP - All succeeding Microsoft instances.

           + 22/TCP - SSH - 1st Linux instance
           + RANDOM/TCP - SSH - All succeeding Linux instances.

          The above replicates the standard behavior of the Azure UI.
          You can retrieve the assigned ports to each instance by
          using the following private function:

          _get_endpoint_ports(service_name)
            Returns public,private port key pair.

           @inherits: :class:`NodeDriver.create_node`

           :keyword     ex_cloud_service_name: Required.
                        Name of the Azure Cloud Service.
           :type        ex_cloud_service_name:  ``str``

           :keyword     ex_storage_service_name: Optional:
                        Name of the Azure Storage Service.
           :type        ex_storage_service_name:  ``str``

           :keyword     ex_deployment_name: Optional. The name of the deployment
                                            If this is not passed in we default
                                            to using the Cloud Service name.
            :type       ex_deployment_name: ``str``

           :keyword     ex_deployment_slot: Optional: Valid values: production|
                                            staging.
                                            Defaults to production.
           :type        ex_deployment_slot:  ``str``

           :keyword     ex_admin_user_id: Optional. Defaults to 'azureuser'.
           :type        ex_admin_user_id:  ``str``

        example endpoint_ports: [{name:'http', 'protocol': 'tcp', 'local_port': 80, 'port': 80},
            {name:'smtp', 'protocol': 'tcp', 'local_port': 25, 'port': 25}] where local_port is the
            private port and port is the public port of the endpoint.


        """
        location = location.id
        image = image.id
        size = size.id

        password = kwargs.get("password", self.random_password())
        name = re.sub(ur'[\W_]+', u'', name.lower(), flags=re.UNICODE)
        #sanitize name

        if not ex_cloud_service_name:
            try:
                self.create_cloud_service(name, location=location)
                ex_cloud_service_name = name
            except:
                #assume the cloud service exists, randomize
                ex_cloud_service_name = name + 'mistio' + str(random.randint(1, 1000))
                self.create_cloud_service(ex_cloud_service_name, location=location)

        if "ex_deployment_slot" in kwargs:
            ex_deployment_slot = kwargs['ex_deployment_slot']
        else:
            # We assume production if this is not provided.
            ex_deployment_slot = "Production"

        if "ex_admin_user_id" in kwargs:
            ex_admin_user_id = kwargs['ex_admin_user_id']
        else:
            # This mimics the Azure UI behavior.
            ex_admin_user_id = "azureuser"
        node_list = self.list_nodes_for_cloud_service(
            ex_cloud_service_name=ex_cloud_service_name)
        network_config = ConfigurationSet()
        network_config.configuration_set_type = 'NetworkConfiguration'

        # We do this because we need to pass a Configuration to the
        # method. This will be either Linux or Windows.
        if re.search("Win|SQL|SharePoint|Visual|Dynamics|DynGP|BizTalk",
                     image, re.I):
            machine_config = WindowsConfigurationSet(
                computer_name=name, admin_password=password,
                admin_user_name=ex_admin_user_id)

            machine_config.domain_join = None

            if node_list == []:
                port = "3389"
            else:
                port = random.randint(41952, 65535)
                endpoints = self._get_deployment(
                    service_name=ex_cloud_service_name,
                    deployment_slot=ex_deployment_slot)

                for instances in endpoints.role_instance_list:
                    ports = []
                    for ep in instances.instance_endpoints:
                        ports += [ep.public_port]

                    while port in ports:
                        port = random.randint(41952, 65535)

            endpoint = ConfigurationSetInputEndpoint(
                name='Remote Desktop',
                protocol='tcp',
                port=port,
                local_port='3389',
                load_balanced_endpoint_set_name=None,
                enable_direct_server_return=False
            )
        else:
            if node_list == []:
                port = "22"
            else:
                port = random.randint(41952, 65535)
                endpoints = self._get_deployment(
                    service_name=ex_cloud_service_name,
                    deployment_slot=ex_deployment_slot)

                for instances in endpoints.role_instance_list:
                    ports = []
                    for ep in instances.instance_endpoints:
                        ports += [ep.public_port]

                    while port in ports:
                        port = random.randint(41952, 65535)

            endpoint = ConfigurationSetInputEndpoint(
                name='SSH',
                protocol='tcp',
                port=port,
                local_port='22',
                load_balanced_endpoint_set_name=None,
                enable_direct_server_return=False
            )
            machine_config = LinuxConfigurationSet(
                name, ex_admin_user_id, password, False, custom_data)

        network_config.input_endpoints.input_endpoints.append(endpoint)


        for endpoint_port in endpoint_ports:
            try:
                input_endpoint = ConfigurationSetInputEndpoint(
                                name=endpoint_port.get('name'),
                                protocol=endpoint_port.get('protocol'),
                                port=endpoint_port.get('port'),
                                local_port=endpoint_port.get('local_port'),
                                load_balanced_endpoint_set_name=None,
                                enable_direct_server_return=False
                            )
                # make sure the endpoint is not duplicate
                if input_endpoint.name != endpoint.name and input_endpoint.port != endpoint.port and \
                    input_endpoint.local_port != endpoint.local_port:
                        network_config.input_endpoints.input_endpoints.append(input_endpoint)
            except:
                pass
        _storage_location = self._get_cloud_service_location(
            service_name=ex_cloud_service_name)


        if "ex_storage_service_name" in kwargs:
            ex_storage_service_name = kwargs['ex_storage_service_name']
        else:
            ex_storage_service_name = ex_cloud_service_name
            ex_storage_service_name = re.sub(
                ur'[\W_]+', u'', ex_storage_service_name.lower(),
                flags=re.UNICODE)
            if self._is_storage_service_unique(
                    service_name=ex_storage_service_name):
                self._create_storage_account(
                    service_name=ex_storage_service_name,
                    location=_storage_location.service_location,
                    is_affinity_group=_storage_location.is_affinity_group
                )
            else:
                ex_storage_service_name = ex_storage_service_name + 'mistio' + str(random.randint(1, 100000))
                self._create_storage_account(
                    service_name=ex_storage_service_name,
                    location=_storage_location.service_location,
                    is_affinity_group=_storage_location.is_affinity_group
                )


        if "ex_deployment_name" in kwargs:
            ex_deployment_name = kwargs['ex_deployment_name']
        else:
            ex_deployment_name = ex_cloud_service_name

        blob_url = "http://" + ex_storage_service_name \
                   + ".blob.core.windows.net"

        # Azure's pattern in the UI.
        disk_name = "{0}-{1}-{2}.vhd".format(
            ex_cloud_service_name, name, time.strftime("%Y-%m-%d"))
        media_link = blob_url + "/vhds/" + disk_name
        disk_config = OSVirtualHardDisk(image, media_link)



        # OK, bit annoying here. You must create a deployment before
        # you can create an instance; however, the deployment function
        # creates the first instance, but all subsequent instances
        # must be created using the add_role function.
        #
        # So, yeah, annoying.
        if node_list == []:
            # This is the first node in this cloud service.
            response = self._perform_post(
                self._get_deployment_path_using_name(ex_cloud_service_name),
                AzureXmlSerializer.virtual_machine_deployment_to_xml(
                    ex_deployment_name,
                    ex_deployment_slot,
                    name,
                    name,
                    machine_config,
                    disk_config,
                    'PersistentVMRole',
                    network_config,
                    None,
                    None,
                    size,
                    None))
        else:
            _deployment_name = self._get_deployment(
                service_name=ex_cloud_service_name,
                deployment_slot=ex_deployment_slot).name

            try:
                response = self._perform_post(
                    self._get_role_path(ex_cloud_service_name,
                                        _deployment_name),
                    AzureXmlSerializer.add_role_to_xml(
                        name,  # role_name
                        machine_config,  # system_config
                        disk_config,  # os_virtual_hard_disk
                        'PersistentVMRole',  # role_type
                        network_config,  # network_config
                        None,  # availability_set_name
                        None,  # data_virtual_hard_disks
                        size))  # role_size)
            except Exception as exc:
                raise LibcloudError('Failed to create node: %r', exc)

        if response.status != 202:
                raise LibcloudError('Message: %s, Body: %s, Status code: %d' %
                                    (response.error, response.body,
                                     response.status), driver=self)

        try:
            self._ex_complete_async_azure_operation(response)
        except:
            pass
            #this might fail for other reasons, but node is created

        return Node(
            id=name,
            name=name,
            state=NodeState.PENDING,
            public_ips=[],
            private_ips=[],
            driver=self.connection.driver,
            extra={'username': ex_admin_user_id, 'password': password}
        )

    def destroy_node(self, node=None, ex_cloud_service_name=None,
                     ex_deployment_slot=None):
        """Remove Azure Virtual Machine

        This removes the instance, but does not
        remove the disk. You will need to use destroy_volume.
        Azure sometimes has an issue where it will hold onto
        a blob lease for an extended amount of time.

        :keyword     ex_cloud_service_name: Required.
                     Name of the Azure Cloud Service.
        :type        ex_cloud_service_name:  ``str``

        :keyword     ex_deployment_slot: Optional: The name of the deployment
                                         slot. If this is not passed in we
                                         default to production.
        :type        ex_deployment_slot:  ``str``
        """

        if not ex_cloud_service_name:
            raise ValueError("ex_cloud_service_name is required.")

        if not node:
            raise ValueError("node is required.")

        if not ex_deployment_slot:
            ex_deployment_slot = "production"

        _deployment = self._get_deployment(
            service_name=ex_cloud_service_name,
            deployment_slot=ex_deployment_slot)

        _deployment_name = _deployment.name

        _server_deployment_count = len(_deployment.role_instance_list)

        if _server_deployment_count > 1:
            path = self._get_role_path(ex_cloud_service_name,
                                       _deployment_name, node.id)
            path += '?comp=media'  # forces deletion of attached disks

            data = self._perform_delete(path)

            return True
        else:
            path = self._get_deployment_path_using_name(
                ex_cloud_service_name,
                _deployment_name)

            path += '?comp=media'

            data = self._perform_delete(path)
            try:
                #also delete cloud service, if this is the only deployment
                self._perform_cloud_service_delete(self._get_hosted_service_path(ex_cloud_service_name))
            except:
                pass


            return True

    def create_cloud_service(self, ex_cloud_service_name=None, location=None,
                             description=None, extended_properties=None):
        """
        creates an azure cloud service.

        :param      ex_cloud_service_name: Cloud Service name
        :type       ex_cloud_service_name: ``str``

        :param      location: standard azure location string
        :type       location: ``str``

        :param      description: optional description
        :type       description: ``str``

        :param      extended_properties: optional extended_properties
        :type       extended_properties: ``dict``

        :rtype: ``bool``
        """
        if not ex_cloud_service_name:
            raise ValueError("ex_cloud_service_name is required.")

        if not location:
            raise ValueError("location is required.")

        response = self._perform_cloud_service_create(
            self._get_hosted_service_path(),
            AzureXmlSerializer.create_hosted_service_to_xml(
                name,
                self._encode_base64(name),
                description,
                location,
                None,
                extended_properties
            )
        )

        self.raise_for_response(response, 201)

        return True

    def ex_destroy_cloud_service(self, name):
        """
        Delete an azure cloud service.

        :param      name: Name of the cloud service to destroy.
        :type       name: ``str``

        :rtype: ``bool``
        """
        response = self._perform_cloud_service_delete(
            self._get_hosted_service_path(name)
        )

        self.raise_for_response(response, 200)

        return True

    def ex_add_instance_endpoints(self, node, endpoints,
                                  ex_deployment_slot="Production"):
        all_endpoints = [
            {
                "name": endpoint.name,
                "protocol": endpoint.protocol,
                "port": endpoint.public_port,
                "local_port": endpoint.local_port,

            }
            for endpoint in node.extra['instance_endpoints']
        ]

        all_endpoints.extend(endpoints)
        # pylint: disable=assignment-from-no-return
        result = self.ex_set_instance_endpoints(node, all_endpoints,
                                                ex_deployment_slot)
        return result

    def ex_set_instance_endpoints(self, node, endpoints,
                                  ex_deployment_slot="Production"):

        """
        For example::

            endpoint = ConfigurationSetInputEndpoint(
                name='SSH',
                protocol='tcp',
                port=port,
                local_port='22',
                load_balanced_endpoint_set_name=None,
                enable_direct_server_return=False
            )
            {
                'name': 'SSH',
                'protocol': 'tcp',
                'port': port,
                'local_port': '22'
            }
        """
        ex_cloud_service_name = node.extra['ex_cloud_service_name']
        vm_role_name = node.name

        network_config = ConfigurationSet()
        network_config.configuration_set_type = 'NetworkConfiguration'

        for endpoint in endpoints:
            new_endpoint = ConfigurationSetInputEndpoint(**endpoint)
            network_config.input_endpoints.items.append(new_endpoint)

        _deployment_name = self._get_deployment(
            service_name=ex_cloud_service_name,
            deployment_slot=ex_deployment_slot
        ).name

        response = self._perform_put(
            self._get_role_path(
                ex_cloud_service_name,
                self._encode_base64(ex_cloud_service_name),
                description, location, None, extended_properties))

        if response.status != 201:
            raise LibcloudError('Message: %s, Body: %s, Status code: %d'
                                % (response.error, response.body,
                                   response.status), driver=self)

        return True

    def destroy_cloud_service(self, ex_cloud_service_name=None):
        """
        deletes an azure cloud service.

        :param      ex_cloud_service_name: Cloud Service name
        :type       ex_cloud_service_name: ``str``

        :rtype: ``bool``
        """

        if not ex_cloud_service_name:
            raise ValueError("ex_cloud_service_name is required.")
        # add check to ensure all nodes have been deleted
        response = self._perform_cloud_service_delete(
            self._get_hosted_service_path(ex_cloud_service_name))

        if response.status != 200:
            raise LibcloudError('Message: %s, Body: %s, Status code: %d' %
                                (response.error, response.body, response.status), driver=self)

        return True

    """ Functions not implemented
    """

    def create_volume_snapshot(self):
        raise NotImplementedError(
            'You cannot create snapshots of '
            'Azure VMs at this time.')

    def attach_volume(self):
        raise NotImplementedError(
            'attach_volume is not supported '
            'at this time.')

    def create_volume(self):
        raise NotImplementedError(
            'create_volume is not supported '
            'at this time.')

    def detach_volume(self):
        raise NotImplementedError(
            'detach_volume is not supported '
            'at this time.')

    def destroy_volume(self):
        raise NotImplementedError(
            'destroy_volume is not supported '
            'at this time.')

    """Private Functions
    """

    def _perform_cloud_service_create(self, path, data):
        request = AzureHTTPRequest()
        request.method = 'POST'
        request.host = azure_service_management_host
        request.path = path
        request.body = data
        request.path, request.query = self._update_request_uri_query(request)
        request.headers = self._update_management_header(request)
        response = self._perform_request(request)

        return response

    def _perform_cloud_service_delete(self, path):
        request = AzureHTTPRequest()
        request.method = 'DELETE'
        request.host = azure_service_management_host
        request.path = path
        request.path, request.query = self._update_request_uri_query(request)
        request.headers = self._update_management_header(request)
        response = self._perform_request(request)

        return response

    def _to_node(self, data):
        """
        Convert the data from a Azure response object into a Node
        """
        if not data.instance_endpoints:
            data.instance_endpoints = []
        if len(data.instance_endpoints) >= 1:
            public_ip = data.instance_endpoints[0].vip
        else:
            public_ip = []

        if public_ip:
            public_ips = [public_ip]
        else:
            public_ips = []
        remote_desktop_port = []
        ssh_port = []
        powershell_port = []
        for port in data.instance_endpoints:
            if port.name == 'Remote Desktop' or 'RdpInput' in port.name:
                remote_desktop_port = port.public_port
            if port.name == 'PowerShell':
                powershell_port = port.public_port
            if port.name == "SSH":
                ssh_port = port.public_port
        if remote_desktop_port or powershell_port:
            os_type = 'windows'
        else:
            os_type = 'linux'

        endpoints = {}
        for endpoint in data.instance_endpoints:
            endpoints[endpoint.name] = '%s:%s %s' % (endpoint.local_port, endpoint.public_port, endpoint.protocol)

        price = get_size_price(driver_type='compute', driver_name='azure_%s' % os_type,
                               size_id=data.instance_size)
        cost_per_hour = None
        if price:
            # TODO: get location from metadata!
            location = 'eastus'
            location = locations_mapping.get(location, 'eastus')
            cost_per_hour = price.get(location)

        return Node(
            id=data.role_name,
            name=data.role_name,
            state=self.NODE_STATE_MAP.get(
                data.instance_status, NodeState.UNKNOWN),
            public_ips=public_ips,
            private_ips=[data.ip_address],
            driver=AzureNodeDriver,
            extra={
                'remote_desktop_port': remote_desktop_port,
                'powershell_port': powershell_port,
                'ssh_port': ssh_port,
                'cost_per_hour': cost_per_hour,
                'os_type': os_type,
                'power_state': data.power_state,
                'instance_size': data.instance_size,
                'endpoints': endpoints})

    def _to_location(self, data):
        """
        Convert the data from a Azure resonse object into a location
        """
        country = data.display_name

        if "Asia" in data.display_name:
            country = "Asia"

        if "Europe" in data.display_name:
            country = "Europe"

        if "US" in data.display_name:
            country = "US"

        if "Japan" in data.display_name:
            country = "Japan"

        if "Brazil" in data.display_name:
            country = "Brazil"

        return AzureNodeLocation(
            id=data.name,
            name=data.display_name,
            country=country,
            driver=self.connection.driver,
            available_services=data.available_services,
            virtual_machine_role_sizes=(data.compute_capabilities).virtual_machines_role_sizes)

    def _to_node_size(self, data):
        """
        Convert the AZURE_COMPUTE_INSTANCE_TYPES into NodeSize
        """
        os_type = 'linux'
        return NodeSize(
            id=data["id"],
            name=data["name"],
            ram=data["ram"],
            disk=data["disk"],
            bandwidth=data["bandwidth"],
            price = get_size_price(driver_type='compute', driver_name='azure_%s' % os_type,
                               size_id=data['id']),
            driver=self.connection.driver,
            extra={
                'max_data_disks': data["max_data_disks"],
                'cores': data["cores"]
            })

    def _to_image(self, data):

        return NodeImage(
            id=data.name,
            name=data.label,
            driver=self.connection.driver,
            extra={
                'os': data.os,
                'category': data.category,
                'description': data.description,
                'location': data.location,
                'affinity_group': data.affinity_group,
                'media_link': data.media_link,
                'show_in_gui': data.show_in_gui,
                'is_premium': data.is_premium
            })

    def _to_volume(self, volume, node):

        if node:
            if hasattr(volume.attached_to, 'role_name'):
                if volume.attached_to.role_name == node.id:
                    extra = {}
                    extra['affinity_group'] = volume.affinity_group
                    if hasattr(volume.attached_to, 'hosted_service_name'):
                        extra['hosted_service_name'] = \
                            volume.attached_to.hosted_service_name
                    if hasattr(volume.attached_to, 'role_name'):
                        extra['role_name'] = volume.attached_to.role_name
                    if hasattr(volume.attached_to, 'deployment_name'):
                        extra['deployment_name'] = \
                            volume.attached_to.deployment_name
                    extra['os'] = volume.os
                    extra['location'] = volume.location
                    extra['media_link'] = volume.media_link
                    extra['source_image_name'] = volume.source_image_name

                    return StorageVolume(id=volume.name,
                                         name=volume.name,
                                         size=int(
                                             volume.logical_disk_size_in_gb),
                                         driver=self.connection.driver,
                                         extra=extra)
        else:
            extra = {}
            extra['affinity_group'] = volume.affinity_group
            if hasattr(volume.attached_to, 'hosted_service_name'):
                extra['hosted_service_name'] = \
                    volume.attached_to.hosted_service_name
            if hasattr(volume.attached_to, 'role_name'):
                extra['role_name'] = volume.attached_to.role_name
            if hasattr(volume.attached_to, 'deployment_name'):
                extra['deployment_name'] = volume.attached_to.deployment_name
            extra['os'] = volume.os
            extra['location'] = volume.location
            extra['media_link'] = volume.media_link
            extra['source_image_name'] = volume.source_image_name

            return StorageVolume(id=volume.name,
                                 name=volume.name,
                                 size=int(volume.logical_disk_size_in_gb),
                                 driver=self.connection.driver,
                                 extra=extra)

    def _get_deployment(self, **kwargs):
        _service_name = kwargs['service_name']
        _deployment_slot = kwargs['deployment_slot']

        response = self._perform_get(
            self._get_deployment_path_using_slot(
                _service_name, _deployment_slot), None)

        if response.status != 200:
            raise LibcloudError('Message: %s, Body: %s, Status code: %d' %
                                (response.error, response.body, response.status), driver=self)

        return self._parse_response(response, Deployment)

    def _get_cloud_service_location(self, service_name=None):

        if not service_name:
            raise ValueError("service_name is required.")

        res = self._perform_get(
            self._get_hosted_service_path(service_name) +
            '?embed-detail=False',
            HostedService)

        _affinity_group = res.hosted_service_properties.affinity_group
        _cloud_service_location = res.hosted_service_properties.location

        if _affinity_group is not None and _affinity_group != '':
            return self.service_location(True, _affinity_group)
        elif _cloud_service_location is not None:
            return self.service_location(False, _cloud_service_location)
        else:
            return None

    def _is_storage_service_unique(self, service_name=None):
        if not service_name:
            raise ValueError("service_name is required.")

        _check_availability = self._perform_get(
            self._get_storage_service_path() +
            '/operations/isavailable/' +
            _str(service_name) + '',
            AvailabilityResponse)

        return _check_availability.result

    def _create_storage_account(self, **kwargs):
        if kwargs['is_affinity_group'] is True:
            response = self._perform_post(
                self._get_storage_service_path(),
                AzureXmlSerializer.create_storage_service_input_to_xml(
                    kwargs['service_name'],
                    kwargs['service_name'],
                    self._encode_base64(kwargs['service_name']),
                    kwargs['location'],
                    None,  # Location
                    True,  # geo_replication_enabled
                    None))  # extended_properties

            if response.status != 202:
                raise LibcloudError('Message: %s, Body: %s, Status code: %d' %
                                    (response.error, response.body,
                                     response.status), driver=self)

        else:
            response = self._perform_post(
                self._get_storage_service_path(),
                AzureXmlSerializer.create_storage_service_input_to_xml(
                    kwargs['service_name'],
                    kwargs['service_name'],
                    self._encode_base64(kwargs['service_name']),
                    None,  # Affinity Group
                    kwargs['location'],  # Location
                    True,  # geo_replication_enabled
                    None))  # extended_properties

            if response.status != 202:
                raise LibcloudError('Message: %s, Body: %s, Status code: %d' %
                                    (response.error, response.body,
                                     response.status), driver=self)

        # We need to wait for this to be created before we can
        # create the storage container and the instance.
        self._ex_complete_async_azure_operation(response,
                                                "create_storage_account")

        return

    def _get_operation_status(self, request_id):
        return self._perform_get(
            '/' + self.subscription_id + '/operations/' + _str(request_id),
            Operation)

    def _perform_get(self, path, response_type):
        request = AzureHTTPRequest()
        request.method = 'GET'
        request.host = azure_service_management_host
        request.path = path
        request.path, request.query = self._update_request_uri_query(request)
        request.headers = self._update_management_header(request)
        #Ugly patch. Azure many times returns an empty response (!) for no reason.
        #Probably due to many simultaneous requests?
        #In these cases try again as fallback
        for i in range(3):
            response = self._perform_request(request)
            if response.body != '':
                break
        if response_type is not None:
            return self._parse_response(response, response_type)

        return response

    def _perform_post(self, path, body, response_type=None):
        request = AzureHTTPRequest()
        request.method = 'POST'
        request.host = azure_service_management_host
        request.path = path
        request.body = ensure_string(self._get_request_body(body))
        request.path, request.query = self._update_request_uri_query(request)
        request.headers = self._update_management_header(request)
        response = self._perform_request(request)

        return response

    def _perform_put(self, path, body, response_type=None):
        request = AzureHTTPRequest()
        request.method = 'PUT'
        request.host = azure_service_management_host
        request.path = path
        request.body = self._get_request_body(body)
        request.path, request.query = \
            self._update_request_uri_query(request)
        request.headers = self._update_management_header(request)
        response = self._perform_request(request)

        return response

    def _perform_delete(self, path):
        request = AzureHTTPRequest()
        request.method = 'DELETE'
        request.host = azure_service_management_host
        request.path = path
        request.path, request.query = self._update_request_uri_query(request)
        request.headers = self._update_management_header(request)
        response = self._perform_request(request)

        if response.status != 202:
            raise LibcloudError('Message: %s, Body: %s, Status code: %d' %
                                (response.error, response.body, response.status), driver=self)

    def _perform_request(self, request):
        try:
            return self.connection.request(
                action=request.path,
                data=request.body,
                headers=request.headers,
                method=request.method
            )
        except AzureRedirectException as e:
            parsed_url = urlparse.urlparse(e.location)
            request.host = parsed_url.netloc
            return self._perform_request(request)
        except Exception as e:
            raise e

    def _update_request_uri_query(self, request):
        '''pulls the query string out of the URI and moves it into
        the query portion of the request object.  If there are already
        query parameters on the request the parameters in the URI will
        appear after the existing parameters'''

        if '?' in request.path:
            request.path, _, query_string = request.path.partition('?')
            if query_string:
                query_params = query_string.split('&')
                for query in query_params:
                    if '=' in query:
                        name, _, value = query.partition('=')
                        request.query.append((name, value))

        request.path = url_quote(request.path, '/()$=\',')

        # add encoded queries to request.path.
        if request.query:
            request.path += '?'
            for name, value in request.query:
                if value is not None:
                    request.path += name + '=' + \
                        url_quote(value, '/()$=\',') + '&'
            request.path = request.path[:-1]

        return request.path, request.query

    def _update_management_header(self, request):
        ''' Add additional headers for management. '''

        if request.method in ['PUT', 'POST', 'MERGE', 'DELETE']:
            request.headers['Content-Length'] = str(len(request.body))

        # append additional headers base on the service
        #request.headers.append(('x-ms-version', X_MS_VERSION))

        # if it is not GET or HEAD request, must set content-type.
        if not request.method in ['GET', 'HEAD']:
            for key in request.headers:
                if 'content-type' == key.lower():
                    break
            else:
                request.headers['Content-Type'] = 'application/xml'

        return request.headers

    def send_request_headers(self, connection, request_headers):
        for name, value in request_headers:
            if value:
                connection.putheader(name, value)

        connection.putheader('User-Agent', _USER_AGENT_STRING)
        connection.endheaders()

    def send_request_body(self, connection, request_body):
        if request_body:
            assert isinstance(request_body, bytes)
            connection.send(request_body)
        elif (not isinstance(connection, HTTPSConnection) and
              not isinstance(connection, httplib.HTTPConnection)):
            connection.send(None)

    def _parse_response(self, response, return_type):
        '''
        Parse the HTTPResponse's body and fill all the data into a class of
        return_type.
        '''
        return self._parse_response_body_from_xml_text(
            response.body, return_type)

    def _parse_response_body_from_xml_text(self, respbody, return_type):
        '''
        parse the xml and fill all the data into a class of return_type
        '''
        try:
            doc = minidom.parseString(respbody.encode('utf-8'))
        except:
            return ''
        return_obj = return_type()
        for node in self._get_child_nodes(doc, return_type.__name__):
            self._fill_data_to_return_object(node, return_obj)

        return return_obj

    def _get_child_nodes(self, node, tagName):
        return [childNode for childNode in node.getElementsByTagName(tagName)
                if childNode.parentNode == node]

    def _fill_data_to_return_object(self, node, return_obj):
        members = dict(vars(return_obj))
        for name, value in members.items():
            if isinstance(value, _list_of):
                setattr(return_obj,
                        name,
                        self._fill_list_of(node,
                                           value.list_type,
                                           value.xml_element_name))
            elif isinstance(value, _scalar_list_of):
                setattr(return_obj,
                        name,
                        self._fill_scalar_list_of(node,
                                                  value.list_type,
                                                  self._get_serialization_name(
                                                      name),
                                                  value.xml_element_name))
            elif isinstance(value, _dict_of):
                setattr(return_obj,
                        name,
                        self._fill_dict_of(node,
                                           self._get_serialization_name(name),
                                           value.pair_xml_element_name,
                                           value.key_xml_element_name,
                                           value.value_xml_element_name))
            elif isinstance(value, WindowsAzureData):
                setattr(return_obj,
                        name,
                        self._fill_instance_child(node, name, value.__class__))
            elif isinstance(value, dict):
                setattr(return_obj,
                        name,
                        self._fill_dict(node,
                                        self._get_serialization_name(name)))
            elif isinstance(value, _Base64String):
                value = self._fill_data_minidom(node, name, '')
                if value is not None:
                    value = self._decode_base64_to_text(value)
                # always set the attribute,
                # so we don't end up returning an object
                # with type _Base64String
                setattr(return_obj, name, value)
            else:
                value = self._fill_data_minidom(node, name, value)
                if value is not None:
                    setattr(return_obj, name, value)

    def _fill_list_of(self, xmldoc, element_type, xml_element_name):
        xmlelements = self._get_child_nodes(xmldoc, xml_element_name)
        return [self._parse_response_body_from_xml_node(
            xmlelement, element_type)
            for xmlelement in xmlelements]

    def _parse_response_body_from_xml_node(self, node, return_type):
        '''
        parse the xml and fill all the data into a class of return_type
        '''
        return_obj = return_type()
        self._fill_data_to_return_object(node, return_obj)

        return return_obj

    def _fill_scalar_list_of(self, xmldoc, element_type, parent_xml_element_name,
                             xml_element_name):
        xmlelements = self._get_child_nodes(xmldoc, parent_xml_element_name)
        if xmlelements:
            xmlelements = \
                self._get_child_nodes(xmlelements[0], xml_element_name)
            return [self._get_node_value(xmlelement, element_type)
                    for xmlelement in xmlelements]

    def _get_node_value(self, xmlelement, data_type):
        value = xmlelement.firstChild.nodeValue
        if data_type is datetime:
            return self._to_datetime(value)
        elif data_type is bool:
            return value.lower() != 'false'
        else:
            return data_type(value)

    def _get_serialization_name(self, element_name):
        """converts a Python name into a serializable name"""
        known = _KNOWN_SERIALIZATION_XFORMS.get(element_name)
        if known is not None:
            return known

        if element_name.startswith('x_ms_'):
            return element_name.replace('_', '-')
        if element_name.endswith('_id'):
            element_name = element_name.replace('_id', 'ID')
        for name in ['content_', 'last_modified', 'if_', 'cache_control']:
            if element_name.startswith(name):
                element_name = element_name.replace('_', '-_')

        return ''.join(name.capitalize() for name in element_name.split('_'))

    def _fill_dict_of(
        self, xmldoc, parent_xml_element_name, pair_xml_element_name,
            key_xml_element_name, value_xml_element_name):
        return_obj = {}

        xmlelements = self._get_child_nodes(xmldoc, parent_xml_element_name)
        if xmlelements:
            xmlelements = \
                self._get_child_nodes(xmlelements[0], pair_xml_element_name)
            for pair in xmlelements:
                keys = self._get_child_nodes(pair, key_xml_element_name)
                values = self._get_child_nodes(pair, value_xml_element_name)
                if keys and values:
                    key = keys[0].firstChild.nodeValue
                    value = values[0].firstChild.nodeValue
                    return_obj[key] = value

        return return_obj

    def _fill_instance_child(self, xmldoc, element_name, return_type):
        '''Converts a child of the current dom element to the specified type.
        '''
        xmlelements = self._get_child_nodes(
            xmldoc, self._get_serialization_name(element_name))

        if not xmlelements:
            return None

        return_obj = return_type()
        self._fill_data_to_return_object(xmlelements[0], return_obj)

        return return_obj

    def _fill_dict(self, xmldoc, element_name):
        xmlelements = self._get_child_nodes(xmldoc, element_name)
        if xmlelements:
            return_obj = {}
            for child in xmlelements[0].childNodes:
                if child.firstChild:
                    return_obj[child.nodeName] = child.firstChild.nodeValue
            return return_obj

    def _encode_base64(self, data):
        if isinstance(data, _unicode_type):
            data = data.encode('utf-8')
        encoded = base64.b64encode(data)
        return encoded.decode('utf-8')

    def _decode_base64_to_bytes(self, data):
        if isinstance(data, _unicode_type):
            data = data.encode('utf-8')
        return base64.b64decode(data)

    def _decode_base64_to_text(self, data):
        decoded_bytes = self._decode_base64_to_bytes(data)
        return decoded_bytes.decode('utf-8')

    def _fill_data_minidom(self, xmldoc, element_name, data_member):
        xmlelements = self._get_child_nodes(
            xmldoc, self._get_serialization_name(element_name))

        if not xmlelements or not xmlelements[0].childNodes:
            return None

        value = xmlelements[0].firstChild.nodeValue

        if data_member is None:
            return value
        elif isinstance(data_member, datetime):
            return self._to_datetime(value)
        elif type(data_member) is bool:
            return value.lower() != 'false'
        else:
            return type(data_member)(value)

    def _to_datetime(self, strtime):
        return datetime.strptime(strtime, "%Y-%m-%dT%H:%M:%S.%f")

    def _get_request_body(self, request_body):
        if request_body is None:
            return b''

        if isinstance(request_body, WindowsAzureData):
            request_body = self._convert_class_to_xml(request_body)

        if isinstance(request_body, bytes):
            return request_body

        if isinstance(request_body, _unicode_type):
            return request_body.encode('utf-8')

        request_body = str(request_body)
        if isinstance(request_body, _unicode_type):
            return request_body.encode('utf-8')

        return request_body

    def _convert_class_to_xml(self, source, xml_prefix=True):
        if source is None:
            return ''

        xmlstr = ''
        if xml_prefix:
            xmlstr = '<?xml version="1.0" encoding="utf-8"?>'

        if isinstance(source, list):
            for value in source:
                xmlstr += self._convert_class_to_xml(value, False)
        elif isinstance(source, WindowsAzureData):
            class_name = source.__class__.__name__
            xmlstr += '<' + class_name + '>'
            for name, value in vars(source).items():
                if value is not None:
                    if isinstance(value, list) or \
                            isinstance(value, WindowsAzureData):
                        xmlstr += self._convert_class_to_xml(value, False)
                    else:
                        xmlstr += ('<' + self._get_serialization_name(name) +
                                   '>' + xml_escape(str(value)) + '</' +
                                   self._get_serialization_name(name) + '>')
            xmlstr += '</' + class_name + '>'
        return xmlstr

    def _parse_response_for_async_op(self, response):
        if response is None:
            return None

        result = AsynchronousOperationResult()
        if response.headers:
            for name, value in response.headers.items():
                if name.lower() == 'x-ms-request-id':
                    result.request_id = value

        return result

    def _get_deployment_path_using_name(self, service_name,
                                        deployment_name=None):
        return self._get_path('services/hostedservices/'
                              + _str(service_name) +
                              '/deployments', deployment_name)

    def _get_path(self, resource, name):
        path = '/' + self.subscription_id + '/' + resource
        if name is not None:
            path += '/' + _str(name)
        return path

    def _get_image_path(self, image_name=None):
        return self._get_path('services/images', image_name)

    def _get_hosted_service_path(self, service_name=None):
        return self._get_path('services/hostedservices', service_name)

    def _get_deployment_path_using_slot(self, service_name, slot=None):
        return self._get_path('services/hostedservices/' + _str(service_name) +
                              '/deploymentslots', slot)

    def _get_disk_path(self, disk_name=None):
        return self._get_path('services/disks', disk_name)

    def _get_role_path(self, service_name, deployment_name, role_name=None):
        return self._get_path('services/hostedservices/' + _str(service_name) +
                              '/deployments/' + deployment_name +
                              '/roles', role_name)

    def _get_storage_service_path(self, service_name=None):
        return self._get_path('services/storageservices', service_name)

    def _ex_complete_async_azure_operation(self, response=None,
                                           operation_type='create_node'):

        request_id = self._parse_response_for_async_op(response)
        operation_status = self._get_operation_status(request_id.request_id)

        timeout = 60 * 5
        waittime = 0
        interval = 5

        while operation_status.status == "InProgress" and waittime < timeout:
            operation_status = self._get_operation_status(request_id)
            if operation_status.status == "Succeeded":
                break

            waittime += interval
            time.sleep(interval)

        if operation_status.status == 'Failed':
            raise LibcloudError(
                'Message: Async request for operation %s has failed' %
                operation_type, driver=self)

    def get_cloud_service_from_node_id(self, node_id):
        "Return cloud service for a node. Used in reboot/destroy/stop/start"
        for service in self.ex_list_cloud_services():
            nodes = self.list_nodes(ex_cloud_service_name=service)
            for node in nodes:
                if node.id == node_id:
                    return service
        return None

    def random_password(self):
        "provide a random valid password for Azure"
        random_char = "!@#$%^*()_+"[random.randint(0,10)]
        random_int = random.randint(0,10)
        random_lower = ''
        for i in range(8):
            random_lower += "abcdefghijklmnopqrstuvwxyz"[random.randint(0,25)]
        random_upper = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[random.randint(0,25)]
        return random_lower + random_upper + str(random_int) + random_char

    # def get_connection(self):
    #    certificate_path = "/Users/baldwin/.azure/managementCertificate.pem"
    #    port = HTTPS_PORT

    #    connection = HTTPSConnection(
    #        azure_service_management_host,
    #        int(port),
    #        cert_file=certificate_path)

    #    return connection


"""
XML Serializer

Borrowed from the Azure SDK for Python which is licensed under Apache 2.0.

https://github.com/Azure/azure-sdk-for-python
"""


def _lower(text):
    return text.lower()


class AzureXmlSerializer():

    @staticmethod
    def create_storage_service_input_to_xml(service_name, description, label,
                                            affinity_group, location,
                                            geo_replication_enabled,
                                            extended_properties):
        return AzureXmlSerializer.doc_from_data(
            'CreateStorageServiceInput',
            [('ServiceName', service_name),
             ('Description', description),
             ('Label', label),
             ('AffinityGroup', affinity_group),
             ('Location', location),
             ('GeoReplicationEnabled', geo_replication_enabled, _lower)],
            extended_properties)

    @staticmethod
    def update_storage_service_input_to_xml(description, label,
                                            geo_replication_enabled,
                                            extended_properties):
        return AzureXmlSerializer.doc_from_data(
            'UpdateStorageServiceInput',
            [('Description', description),
             ('Label', label, AzureNodeDriver._encode_base64),
             ('GeoReplicationEnabled', geo_replication_enabled, _lower)],
            extended_properties)

    @staticmethod
    def regenerate_keys_to_xml(key_type):
        return AzureXmlSerializer.doc_from_data('RegenerateKeys',
                                                [('KeyType', key_type)])

    @staticmethod
    def update_hosted_service_to_xml(label, description, extended_properties):
        return AzureXmlSerializer.doc_from_data('UpdateHostedService',
                                                [('Label', label,
                                                  AzureNodeDriver._encode_base64),
                                                 ('Description', description)],
                                                extended_properties)

    @staticmethod
    def create_hosted_service_to_xml(service_name, label, description,
                                     location, affinity_group,
                                     extended_properties):
        return AzureXmlSerializer.doc_from_data(
            'CreateHostedService',
            [('ServiceName', service_name),
             ('Label', label),
             ('Description', description),
             ('Location', location),
             ('AffinityGroup', affinity_group)],
            extended_properties)

    @staticmethod
    def create_deployment_to_xml(name, package_url, label, configuration,
                                 start_deployment, treat_warnings_as_error,
                                 extended_properties):
        return AzureXmlSerializer.doc_from_data(
            'CreateDeployment',
            [('Name', name),
             ('PackageUrl', package_url),
             ('Label', label, AzureNodeDriver._encode_base64),
             ('Configuration', configuration),
             ('StartDeployment',
              start_deployment, _lower),
             ('TreatWarningsAsError', treat_warnings_as_error, _lower)],
            extended_properties)

    @staticmethod
    def swap_deployment_to_xml(production, source_deployment):
        return AzureXmlSerializer.doc_from_data(
            'Swap',
            [('Production', production),
             ('SourceDeployment', source_deployment)])

    @staticmethod
    def update_deployment_status_to_xml(status):
        return AzureXmlSerializer.doc_from_data(
            'UpdateDeploymentStatus',
            [('Status', status)])

    @staticmethod
    def change_deployment_to_xml(configuration, treat_warnings_as_error, mode,
                                 extended_properties):
        return AzureXmlSerializer.doc_from_data(
            'ChangeConfiguration',
            [('Configuration', configuration),
             ('TreatWarningsAsError', treat_warnings_as_error, _lower),
             ('Mode', mode)],
            extended_properties)

    @staticmethod
    def upgrade_deployment_to_xml(mode, package_url, configuration, label,
                                  role_to_upgrade, force, extended_properties):
        return AzureXmlSerializer.doc_from_data(
            'UpgradeDeployment',
            [('Mode', mode),
             ('PackageUrl', package_url),
             ('Configuration', configuration),
             ('Label', label, AzureNodeDriver._encode_base64),
             ('RoleToUpgrade', role_to_upgrade),
             ('Force', force, _lower)],
            extended_properties)

    @staticmethod
    def rollback_upgrade_to_xml(mode, force):
        return AzureXmlSerializer.doc_from_data(
            'RollbackUpdateOrUpgrade',
            [('Mode', mode),
             ('Force', force, _lower)])

    @staticmethod
    def walk_upgrade_domain_to_xml(upgrade_domain):
        return AzureXmlSerializer.doc_from_data(
            'WalkUpgradeDomain',
            [('UpgradeDomain', upgrade_domain)])

    @staticmethod
    def certificate_file_to_xml(data, certificate_format, password):
        return AzureXmlSerializer.doc_from_data(
            'CertificateFile',
            [('Data', data),
             ('CertificateFormat', certificate_format),
             ('Password', password)])

    @staticmethod
    def create_affinity_group_to_xml(name, label, description, location):
        return AzureXmlSerializer.doc_from_data(
            'CreateAffinityGroup',
            [('Name', name),
             ('Label', label, AzureNodeDriver._encode_base64),
             ('Description', description),
             ('Location', location)])

    @staticmethod
    def update_affinity_group_to_xml(label, description):
        return AzureXmlSerializer.doc_from_data(
            'UpdateAffinityGroup',
            [('Label', label, AzureNodeDriver._encode_base64),
             ('Description', description)])

    @staticmethod
    def subscription_certificate_to_xml(public_key, thumbprint, data):
        return AzureXmlSerializer.doc_from_data(
            'SubscriptionCertificate',
            [('SubscriptionCertificatePublicKey', public_key),
             ('SubscriptionCertificateThumbprint', thumbprint),
             ('SubscriptionCertificateData', data)])

    @staticmethod
    def os_image_to_xml(label, media_link, name, os, showingui, ispremium):
        return AzureXmlSerializer.doc_from_data(
            'OSImage',
            [('Label', label),
             ('MediaLink', media_link),
             ('Name', name),
             ('OS', os),
             ('ShowInGui', showingui),
             ('IsPremium', ispremium)])

    @staticmethod
    def data_virtual_hard_disk_to_xml(host_caching, disk_label, disk_name, lun,
                                      logical_disk_size_in_gb, media_link,
                                      source_media_link):
        return AzureXmlSerializer.doc_from_data(
            'DataVirtualHardDisk',
            [('HostCaching', host_caching),
             ('DiskLabel', disk_label),
             ('DiskName', disk_name),
             ('Lun', lun),
             ('LogicalDiskSizeInGB', logical_disk_size_in_gb),
             ('MediaLink', media_link),
             ('SourceMediaLink', source_media_link)])

    @staticmethod
    def disk_to_xml(has_operating_system, label, media_link, name, os):
        return AzureXmlSerializer.doc_from_data(
            'Disk',
            [('HasOperatingSystem', has_operating_system, _lower),
             ('Label', label),
             ('MediaLink', media_link),
             ('Name', name),
             ('OS', os)])

    @staticmethod
    def restart_role_operation_to_xml():
        return AzureXmlSerializer.doc_from_xml(
            'RestartRoleOperation',
            '<OperationType>RestartRoleOperation</OperationType>')

    @staticmethod
    def shutdown_role_operation_to_xml():
        return AzureXmlSerializer.doc_from_xml(
            'ShutdownRoleOperation',
            '<OperationType>ShutdownRoleOperation</OperationType>')

    @staticmethod
    def start_role_operation_to_xml():
        return AzureXmlSerializer.doc_from_xml(
            'StartRoleOperation',
            xml
        )
        result = ensure_string(ET.tostring(doc, encoding='utf-8'))
        return result

    @staticmethod
    def windows_configuration_to_xml(configuration, xml):
        AzureXmlSerializer.data_to_xml(
            [('ConfigurationSetType', configuration.configuration_set_type)],
            xml
        )
        AzureXmlSerializer.data_to_xml(
            [('ComputerName', configuration.computer_name)],
            xml
        )
        AzureXmlSerializer.data_to_xml(
            [('AdminPassword', configuration.admin_password)],
            xml
        )
        AzureXmlSerializer.data_to_xml(
            [
                (
                    'ResetPasswordOnFirstLogon',
                    configuration.reset_password_on_first_logon,
                    _lower
                )
            ],
            xml
        )

        AzureXmlSerializer.data_to_xml(
            [
                (
                    'EnableAutomaticUpdates',
                    configuration.enable_automatic_updates,
                    _lower
                )
            ],
            xml
        )

        AzureXmlSerializer.data_to_xml(
            [('TimeZone', configuration.time_zone)],
            xml
        )

        if configuration.domain_join is not None:
            domain = ET.xml("DomainJoin")  # pylint: disable=no-member
            creds = ET.xml("Credentials")  # pylint: disable=no-member
            domain.appemnd(creds)
            xml.append(domain)

            AzureXmlSerializer.data_to_xml(
                [('Domain', configuration.domain_join.credentials.domain)],
                creds
            )

            AzureXmlSerializer.data_to_xml(
                [
                    (
                        'Username',
                        configuration.domain_join.credentials.username
                    )
                ],
                creds
            )
            AzureXmlSerializer.data_to_xml(
                [
                    (
                        'Password',
                        configuration.domain_join.credentials.password
                    )
                ],
                creds
            )

            AzureXmlSerializer.data_to_xml(
                [('JoinDomain', configuration.domain_join.join_domain)],
                domain
            )

            AzureXmlSerializer.data_to_xml(
                [
                    (
                        'MachineObjectOU',
                        configuration.domain_join.machine_object_ou
                    )
                ],
                domain
            )

        if configuration.stored_certificate_settings is not None:
            cert_settings = ET.Element("StoredCertificateSettings")
            xml.append(cert_settings)
            for cert in configuration.stored_certificate_settings:
                cert_setting = ET.Element("CertificateSetting")
                cert_settings.append(cert_setting)

                cert_setting.append(AzureXmlSerializer.data_to_xml(
                    [('StoreLocation', cert.store_location)])
                )
                AzureXmlSerializer.data_to_xml(
                    [('StoreName', cert.store_name)],
                    cert_setting
                )
                AzureXmlSerializer.data_to_xml(
                    [('Thumbprint', cert.thumbprint)],
                    cert_setting
                )

        AzureXmlSerializer.data_to_xml(
            [('AdminUsername', configuration.admin_user_name)],
            xml
        )
        return xml

    @staticmethod
    def linux_configuration_to_xml(configuration, xml):
        AzureXmlSerializer.data_to_xml(
            [('ConfigurationSetType', configuration.configuration_set_type)],
            xml
        )
        AzureXmlSerializer.data_to_xml(
            [('HostName', configuration.host_name)],
            xml
        )
        AzureXmlSerializer.data_to_xml(
            [('UserName', configuration.user_name)],
            xml
        )
        AzureXmlSerializer.data_to_xml(
            [('UserPassword', configuration.user_password)],
            xml
        )
        AzureXmlSerializer.data_to_xml(
            [
                (
                    'DisableSshPasswordAuthentication',
                    configuration.disable_ssh_password_authentication,
                    _lower
                )
            ],
            xml
        )

        if configuration.ssh is not None:
            ssh = ET.Element("SSH")
            pkeys = ET.Element("PublicKeys")
            kpairs = ET.Element("KeyPairs")
            ssh.append(pkeys)
            ssh.append(kpairs)
            xml.append(ssh)

            for key in configuration.ssh.public_keys:
                pkey = ET.Element("PublicKey")
                pkeys.append(pkey)
                AzureXmlSerializer.data_to_xml(
                    [('Fingerprint', key.fingerprint)],
                    pkey
                )
                AzureXmlSerializer.data_to_xml([('Path', key.path)], pkey)

            for key in configuration.ssh.key_pairs:
                kpair = ET.Element("KeyPair")
                kpairs.append(kpair)
                AzureXmlSerializer.data_to_xml(
                    [('Fingerprint', key.fingerprint)],
                    kpair
                )
                AzureXmlSerializer.data_to_xml([('Path', key.path)], kpair)

        if configuration.custom_data is not None:
            AzureXmlSerializer.data_to_xml(
                [('CustomData', configuration.custom_data)],
                xml
            )

        return xml

    @staticmethod
    def network_configuration_to_xml(configuration):
        xml = AzureXmlSerializer.data_to_xml(
            [('ConfigurationSetType', configuration.configuration_set_type)])
        xml += '<InputEndpoints>'
        for endpoint in configuration.input_endpoints:
            xml += '<InputEndpoint>'
            xml += AzureXmlSerializer.data_to_xml(
                [('LoadBalancedEndpointSetName',
                  endpoint.load_balanced_endpoint_set_name),
                 ('LocalPort', endpoint.local_port),
                 ('Name', endpoint.name),
                 ('Port', endpoint.port)])

            if endpoint.load_balancer_probe.path or\
                    endpoint.load_balancer_probe.port or\
                    endpoint.load_balancer_probe.protocol:
                xml += '<LoadBalancerProbe>'
                xml += AzureXmlSerializer.data_to_xml(
                    [('Path', endpoint.load_balancer_probe.path),
                     ('Port', endpoint.load_balancer_probe.port),
                     ('Protocol', endpoint.load_balancer_probe.protocol)])
                xml += '</LoadBalancerProbe>'

            xml += AzureXmlSerializer.data_to_xml(
                [('Protocol', endpoint.protocol),
                 ('EnableDirectServerReturn',
                  endpoint.enable_direct_server_return,
                  _lower)])

            xml += '</InputEndpoint>'
        xml += '</InputEndpoints>'
        xml += '<SubnetNames>'
        for name in configuration.subnet_names:
            xml += AzureXmlSerializer.data_to_xml([('SubnetName', name)])
        xml += '</SubnetNames>'
        return xml

    @staticmethod
    def role_to_xml(availability_set_name, data_virtual_hard_disks,
                    network_configuration_set, os_virtual_hard_disk, role_name,
                    role_size, role_type, system_configuration_set):
        xml = AzureXmlSerializer.data_to_xml([('RoleName', role_name),
                                              ('RoleType', role_type)])

        xml += '<ConfigurationSets>'

        if system_configuration_set is not None:
            xml += '<ConfigurationSet>'
            if isinstance(system_configuration_set, WindowsConfigurationSet):
                xml += AzureXmlSerializer.windows_configuration_to_xml(
                    system_configuration_set)
            elif isinstance(system_configuration_set, LinuxConfigurationSet):
                xml += AzureXmlSerializer.linux_configuration_to_xml(
                    system_configuration_set)
            xml += '</ConfigurationSet>'

        if network_configuration_set is not None:
            xml += '<ConfigurationSet>'
            xml += AzureXmlSerializer.network_configuration_to_xml(
                network_configuration_set)
            xml += '</ConfigurationSet>'

        xml += '</ConfigurationSets>'

        if availability_set_name is not None:
            xml += AzureXmlSerializer.data_to_xml(
                [('AvailabilitySetName', availability_set_name)])

        if data_virtual_hard_disks is not None:
            xml += '<DataVirtualHardDisks>'
            for hd in data_virtual_hard_disks:
                xml += '<DataVirtualHardDisk>'
                xml += AzureXmlSerializer.data_to_xml(
                    [('HostCaching', hd.host_caching),
                     ('DiskLabel', hd.disk_label),
                     ('DiskName', hd.disk_name),
                     ('Lun', hd.lun),
                     ('LogicalDiskSizeInGB', hd.logical_disk_size_in_gb),
                     ('MediaLink', hd.media_link)])
                xml += '</DataVirtualHardDisk>'
            xml += '</DataVirtualHardDisks>'

        if os_virtual_hard_disk is not None:
            xml += '<OSVirtualHardDisk>'
            xml += AzureXmlSerializer.data_to_xml(
                [('HostCaching', os_virtual_hard_disk.host_caching),
                 ('DiskLabel', os_virtual_hard_disk.disk_label),
                 ('DiskName', os_virtual_hard_disk.disk_name),
                 ('MediaLink', os_virtual_hard_disk.media_link),
                 ('SourceImageName', os_virtual_hard_disk.source_image_name)])
            xml += '</OSVirtualHardDisk>'

        if role_size is not None:
            xml += AzureXmlSerializer.data_to_xml([('RoleSize', role_size)])

        return xml

    @staticmethod
    def add_role_to_xml(role_name, system_configuration_set,
                        os_virtual_hard_disk, role_type,
                        network_configuration_set, availability_set_name,
                        data_virtual_hard_disks, role_size):
        xml = AzureXmlSerializer.role_to_xml(
            availability_set_name,
            data_virtual_hard_disks,
            network_configuration_set,
            os_virtual_hard_disk,
            role_name,
            role_size,
            role_type,
            system_configuration_set)
        return AzureXmlSerializer.doc_from_xml('PersistentVMRole', xml)

    @staticmethod
    def update_role_to_xml(role_name, os_virtual_hard_disk, role_type,
                           network_configuration_set, availability_set_name,
                           data_virtual_hard_disks, role_size):
        xml = AzureXmlSerializer.role_to_xml(
            availability_set_name,
            data_virtual_hard_disks,
            network_configuration_set,
            os_virtual_hard_disk,
            role_name,
            role_size,
            role_type,
            None)
        return AzureXmlSerializer.doc_from_xml('PersistentVMRole', xml)

    @staticmethod
    def capture_role_to_xml(post_capture_action, target_image_name,
                            target_image_label, provisioning_configuration):
        xml = AzureXmlSerializer.data_to_xml(
            [('OperationType', 'CaptureRoleOperation'),
             ('PostCaptureAction', post_capture_action)])

        if provisioning_configuration is not None:
            xml += '<ProvisioningConfiguration>'
            if isinstance(provisioning_configuration, WindowsConfigurationSet):
                xml += AzureXmlSerializer.windows_configuration_to_xml(
                    provisioning_configuration)
            elif isinstance(provisioning_configuration, LinuxConfigurationSet):
                xml += AzureXmlSerializer.linux_configuration_to_xml(
                    provisioning_configuration)
            xml += '</ProvisioningConfiguration>'

        xml += AzureXmlSerializer.data_to_xml(
            [('TargetImageLabel', target_image_label),
             ('TargetImageName', target_image_name)])

        return AzureXmlSerializer.doc_from_xml('CaptureRoleOperation', xml)

    @staticmethod
    def virtual_machine_deployment_to_xml(deployment_name, deployment_slot,
                                          label, role_name,
                                          system_configuration_set,
                                          os_virtual_hard_disk, role_type,
                                          network_configuration_set,
                                          availability_set_name,
                                          data_virtual_hard_disks, role_size,
                                          virtual_network_name):
        xml = AzureXmlSerializer.data_to_xml([('Name', deployment_name),
                                              ('DeploymentSlot',
                                               deployment_slot),
                                              ('Label', label)])
        xml += '<RoleList>'
        xml += '<Role>'
        xml += AzureXmlSerializer.role_to_xml(
            availability_set_name,
            data_virtual_hard_disks,
            network_configuration_set,
            os_virtual_hard_disk,
            role_name,
            role_size,
            role_type,
            system_configuration_set)
        xml += '</Role>'
        xml += '</RoleList>'

        if virtual_network_name is not None:
            xml += AzureXmlSerializer.data_to_xml(
                [('VirtualNetworkName', virtual_network_name)])

        return AzureXmlSerializer.doc_from_xml('Deployment', xml)

    @staticmethod
    def data_to_xml(data):
        '''Creates an xml fragment from the specified data.
           data: Array of tuples, where first: xml element name
                                        second: xml element text
                                        third: conversion function
        '''
        xml = ''
        for element in data:
            name = element[0]
            val = element[1]
            if len(element) > 2:
                converter = element[2]
            else:
                converter = None

            if val is not None:
                if converter is not None:
                    text = _str(converter(_str(val)))
                else:
                    text = _str(val)

                xml += ''.join(['<', name, '>', text, '</', name, '>'])
        return xml

    @staticmethod
    def doc_from_xml(document_element_name, inner_xml):
        '''Wraps the specified xml in an xml root element with default azure
        namespaces'''
        xml = ''.join(['<', document_element_name,
                       ' xmlns:i="http://www.w3.org/2001/XMLSchema-instance"',
                       ' xmlns="http://schemas.microsoft.com/windowsazure">'])
        xml += inner_xml
        xml += ''.join(['</', document_element_name, '>'])
        return xml

    @staticmethod
    def doc_from_data(document_element_name, data, extended_properties=None):
        xml = AzureXmlSerializer.data_to_xml(data)
        if extended_properties is not None:
            xml += AzureXmlSerializer.extended_properties_dict_to_xml_fragment(
                extended_properties)
        return AzureXmlSerializer.doc_from_xml(document_element_name, xml)

    @staticmethod
    def extended_properties_dict_to_xml_fragment(extended_properties):
        xml = ''
        if extended_properties is not None and len(extended_properties) > 0:
            xml += '<ExtendedProperties>'
            for key, val in extended_properties.items():
                xml += ''.join(['<ExtendedProperty>',
                                '<Name>',
                                _str(key),
                                '</Name>',
                                '<Value>',
                                _str(val),
                                '</Value>',
                                '</ExtendedProperty>'])
            xml += '</ExtendedProperties>'
        return xml



"""
Data Classes

Borrowed from the Azure SDK for Python.
"""


class WindowsAzureData(object):

    ''' This is the base of data class.
    It is only used to check whether it is instance or not. '''
    pass


class OSVirtualHardDisk(WindowsAzureData):

    def __init__(self, source_image_name=None, media_link=None,
                 host_caching=None, disk_label=None, disk_name=None):
        self.source_image_name = source_image_name
        self.media_link = media_link
        self.host_caching = host_caching
        self.disk_label = disk_label
        self.disk_name = disk_name
        self.os = u''  # undocumented, not used when adding a role


class LinuxConfigurationSet(WindowsAzureData):

    def __init__(self, host_name=None, user_name=None, user_password=None,
                 disable_ssh_password_authentication=None, custom_data=None):
        self.configuration_set_type = u'LinuxProvisioningConfiguration'
        self.host_name = host_name
        self.user_name = user_name
        self.user_password = user_password
        self.disable_ssh_password_authentication =\
            disable_ssh_password_authentication
        self.ssh = SSH()
        self.custom_data = custom_data


class WindowsConfigurationSet(WindowsAzureData):

    def __init__(self, computer_name=None, admin_password=None,
                 reset_password_on_first_logon=None,
                 enable_automatic_updates=None,
                 time_zone=None, admin_user_name=None):
        self.configuration_set_type = u'WindowsProvisioningConfiguration'
        self.computer_name = computer_name
        self.admin_password = admin_password
        self.reset_password_on_first_logon = reset_password_on_first_logon
        self.enable_automatic_updates = enable_automatic_updates
        self.time_zone = time_zone
        self.admin_user_name = admin_user_name
        self.domain_join = DomainJoin()
        self.stored_certificate_settings = StoredCertificateSettings()


class DomainJoin(WindowsAzureData):

    def __init__(self):
        self.credentials = Credentials()
        self.join_domain = u''
        self.machine_object_ou = u''


class Credentials(WindowsAzureData):

    def __init__(self):
        self.domain = u''
        self.username = u''
        self.password = u''


class StoredCertificateSettings(WindowsAzureData):

    def __init__(self):
        self.stored_certificate_settings = _list_of(CertificateSetting)

    def __iter__(self):
        return iter(self.stored_certificate_settings)

    def __len__(self):
        return len(self.stored_certificate_settings)

    def __getitem__(self, index):
        return self.stored_certificate_settings[index]


class CertificateSetting(WindowsAzureData):

    '''
    Initializes a certificate setting.

    thumbprint:
        Specifies the thumbprint of the certificate to be provisioned. The
        thumbprint must specify an existing service certificate.
    store_name:
        Specifies the name of the certificate store from which retrieve
        certificate.
    store_location:
        Specifies the target certificate store location on the virtual machine.
        The only supported value is LocalMachine.
    '''

    def __init__(self, thumbprint=u'', store_name=u'', store_location=u''):
        self.thumbprint = thumbprint
        self.store_name = store_name
        self.store_location = store_location


class SSH(WindowsAzureData):

    def __init__(self):
        self.public_keys = PublicKeys()
        self.key_pairs = KeyPairs()


class PublicKeys(WindowsAzureData):

    def __init__(self):
        self.public_keys = _list_of(PublicKey)

    def __iter__(self):
        return iter(self.public_keys)

    def __len__(self):
        return len(self.public_keys)

    def __getitem__(self, index):
        return self.public_keys[index]


class PublicKey(WindowsAzureData):

    def __init__(self, fingerprint=u'', path=u''):
        self.fingerprint = fingerprint
        self.path = path


class KeyPairs(WindowsAzureData):

    def __init__(self):
        self.key_pairs = _list_of(KeyPair)

    def __iter__(self):
        return iter(self.key_pairs)

    def __len__(self):
        return len(self.key_pairs)

    def __getitem__(self, index):
        return self.key_pairs[index]


class KeyPair(WindowsAzureData):

    def __init__(self, fingerprint=u'', path=u''):
        self.fingerprint = fingerprint
        self.path = path


class LoadBalancerProbe(WindowsAzureData):

    def __init__(self):
        self.path = u''
        self.port = u''
        self.protocol = u''


class ConfigurationSets(WindowsAzureData):

    def __init__(self):
        self.configuration_sets = _list_of(ConfigurationSet)

    def __iter__(self):
        return iter(self.configuration_sets)

    def __len__(self):
        return len(self.configuration_sets)

    def __getitem__(self, index):
        return self.configuration_sets[index]


class ConfigurationSet(WindowsAzureData):

    def __init__(self):
        self.configuration_set_type = u''
        self.role_type = u''
        self.input_endpoints = ConfigurationSetInputEndpoints()
        self.subnet_names = _scalar_list_of(str, 'SubnetName')


class ConfigurationSetInputEndpoints(WindowsAzureData):

    def __init__(self):
        self.input_endpoints = _list_of(
            ConfigurationSetInputEndpoint, 'InputEndpoint')

    def __iter__(self):
        return iter(self.input_endpoints)

    def __len__(self):
        return len(self.input_endpoints)

    def __getitem__(self, index):
        return self.input_endpoints[index]


class ConfigurationSetInputEndpoint(WindowsAzureData):

    def __init__(self, name=u'', protocol=u'', port=u'', local_port=u'',
                 load_balanced_endpoint_set_name=u'',
                 enable_direct_server_return=False):
        self.enable_direct_server_return = enable_direct_server_return
        self.load_balanced_endpoint_set_name = load_balanced_endpoint_set_name
        self.local_port = local_port
        self.name = name
        self.port = port
        self.load_balancer_probe = LoadBalancerProbe()
        self.protocol = protocol


class Locations(WindowsAzureData):

    def __init__(self):
        self.locations = _list_of(Location)

    def __iter__(self):
        return iter(self.locations)

    def __len__(self):
        return len(self.locations)

    def __getitem__(self, index):
        return self.locations[index]


class Location(WindowsAzureData):

    def __init__(self):
        self.name = u''
        self.display_name = u''
        self.available_services = _scalar_list_of(str, 'AvailableService')
        self.compute_capabilities = ComputeCapability()


class ComputeCapability(WindowsAzureData):

    def __init__(self):
        self.virtual_machines_role_sizes = _scalar_list_of(str, 'RoleSize')


class VirtualMachinesRoleSizes(WindowsAzureData):

    def __init__(self):
        self.role_size = _scalar_list_of(str, 'RoleSize')


class Images(WindowsAzureData):

    def __init__(self):
        self.images = _list_of(OSImage)

    def __iter__(self):
        return iter(self.images)

    def __len__(self):
        return len(self.images)

    def __getitem__(self, index):
        return self.images[index]


class OSImage(WindowsAzureData):

    def __init__(self):
        self.affinity_group = u''
        self.category = u''
        self.location = u''
        self.logical_size_in_gb = 0
        self.label = u''
        self.media_link = u''
        self.name = u''
        self.os = u''
        self.eula = u''
        self.show_in_gui = u''
        self.is_premium = u''
        self.description = u''


class HostedServices(WindowsAzureData):

    def __init__(self):
        self.hosted_services = _list_of(HostedService)

    def __iter__(self):
        return iter(self.hosted_services)

    def __len__(self):
        return len(self.hosted_services)

    def __getitem__(self, index):
        return self.hosted_services[index]


class HostedService(WindowsAzureData):

    def __init__(self):
        self.url = u''
        self.service_name = u''
        self.hosted_service_properties = HostedServiceProperties()
        self.deployments = Deployments()


class HostedServiceProperties(WindowsAzureData):

    def __init__(self):
        self.description = u''
        self.location = u''
        self.affinity_group = u''
        self.label = _Base64String()
        self.status = u''
        self.date_created = u''
        self.date_last_modified = u''
        self.extended_properties = _dict_of(
            'ExtendedProperty', 'Name', 'Value')


class Deployments(WindowsAzureData):

    def __init__(self):
        self.deployments = _list_of(Deployment)

    def __iter__(self):
        return iter(self.deployments)

    def __len__(self):
        return len(self.deployments)

    def __getitem__(self, index):
        return self.deployments[index]


class Deployment(WindowsAzureData):

    def __init__(self):
        self.name = u''
        self.deployment_slot = u''
        self.private_id = u''
        self.status = u''
        self.label = _Base64String()
        self.url = u''
        self.configuration = _Base64String()
        self.role_instance_list = RoleInstanceList()
        self.upgrade_status = UpgradeStatus()
        self.upgrade_domain_count = u''
        self.role_list = RoleList()
        self.sdk_version = u''
        self.input_endpoint_list = InputEndpoints()
        self.locked = False
        self.rollback_allowed = False
        self.persistent_vm_downtime_info = PersistentVMDowntimeInfo()
        self.created_time = u''
        self.last_modified_time = u''
        self.extended_properties = _dict_of(
            'ExtendedProperty', 'Name', 'Value')


class UpgradeStatus(WindowsAzureData):

    def __init__(self):
        self.upgrade_type = u''
        self.current_upgrade_domain_state = u''
        self.current_upgrade_domain = u''


class RoleInstanceList(WindowsAzureData):

    def __init__(self):
        self.role_instances = _list_of(RoleInstance)

    def __iter__(self):
        return iter(self.role_instances)

    def __len__(self):
        return len(self.role_instances)

    def __getitem__(self, index):
        return self.role_instances[index]


class RoleInstance(WindowsAzureData):

    def __init__(self):
        self.role_name = u''
        self.instance_name = u''
        self.instance_status = u''
        self.instance_upgrade_domain = 0
        self.instance_fault_domain = 0
        self.instance_size = u''
        self.instance_state_details = u''
        self.instance_error_code = u''
        self.ip_address = u''
        self.instance_endpoints = InstanceEndpoints()
        self.power_state = u''
        self.fqdn = u''
        self.host_name = u''
        self.location = u''


class InstanceEndpoints(WindowsAzureData):

    def __init__(self):
        self.instance_endpoints = _list_of(InstanceEndpoint)

    def __iter__(self):
        return iter(self.instance_endpoints)

    def __len__(self):
        return len(self.instance_endpoints)

    def __getitem__(self, index):
        return self.instance_endpoints[index]


class InstanceEndpoint(WindowsAzureData):

    def __init__(self):
        self.name = u''
        self.vip = u''
        self.public_port = u''
        self.local_port = u''
        self.protocol = u''


class InputEndpoints(WindowsAzureData):

    def __init__(self):
        self.input_endpoints = _list_of(InputEndpoint)

    def __iter__(self):
        return iter(self.input_endpoints)

    def __len__(self):
        return len(self.input_endpoints)

    def __getitem__(self, index):
        return self.input_endpoints[index]


class InputEndpoint(WindowsAzureData):

    def __init__(self):
        self.role_name = u''
        self.vip = u''
        self.port = u''


class RoleList(WindowsAzureData):

    def __init__(self):
        self.roles = _list_of(Role)

    def __iter__(self):
        return iter(self.roles)

    def __len__(self):
        return len(self.roles)

    def __getitem__(self, index):
        return self.roles[index]


class Role(WindowsAzureData):

    def __init__(self):
        self.role_name = u''
        self.os_version = u''


class PersistentVMDowntimeInfo(WindowsAzureData):

    def __init__(self):
        self.start_time = u''
        self.end_time = u''
        self.status = u''


class AsynchronousOperationResult(WindowsAzureData):

    def __init__(self, request_id=None):
        self.request_id = request_id


class Disks(WindowsAzureData):

    def __init__(self):
        self.disks = _list_of(Disk)

    def __iter__(self):
        return iter(self.disks)

    def __len__(self):
        return len(self.disks)

    def __getitem__(self, index):
        return self.disks[index]


class Disk(WindowsAzureData):

    def __init__(self):
        self.affinity_group = u''
        self.attached_to = AttachedTo()
        self.has_operating_system = u''
        self.is_corrupted = u''
        self.location = u''
        self.logical_disk_size_in_gb = 0
        self.label = u''
        self.media_link = u''
        self.name = u''
        self.os = u''
        self.source_image_name = u''


class AttachedTo(WindowsAzureData):

    def __init__(self):
        self.hosted_service_name = u''
        self.deployment_name = u''
        self.role_name = u''


class OperationError(WindowsAzureData):

    def __init__(self):
        self.code = u''
        self.message = u''


class Operation(WindowsAzureData):

    def __init__(self):
        self.id = u''
        self.status = u''
        self.http_status_code = u''
        self.error = OperationError()


class OperatingSystem(WindowsAzureData):

    def __init__(self):
        self.version = u''
        self.label = _Base64String()
        self.is_default = True
        self.is_active = True
        self.family = 0
        self.family_label = _Base64String()


class OperatingSystems(WindowsAzureData):

    def __init__(self):
        self.operating_systems = _list_of(OperatingSystem)

    def __iter__(self):
        return iter(self.operating_systems)

    def __len__(self):
        return len(self.operating_systems)

    def __getitem__(self, index):
        return self.operating_systems[index]


class OperatingSystemFamily(WindowsAzureData):

    def __init__(self):
        self.name = u''
        self.label = _Base64String()
        self.operating_systems = OperatingSystems()


class OperatingSystemFamilies(WindowsAzureData):

    def __init__(self):
        self.operating_system_families = _list_of(OperatingSystemFamily)

    def __iter__(self):
        return iter(self.operating_system_families)

    def __len__(self):
        return len(self.operating_system_families)

    def __getitem__(self, index):
        return self.operating_system_families[index]


class Subscription(WindowsAzureData):

    def __init__(self):
        self.subscription_id = u''
        self.subscription_name = u''
        self.subscription_status = u''
        self.account_admin_live_email_id = u''
        self.service_admin_live_email_id = u''
        self.max_core_count = 0
        self.max_storage_accounts = 0
        self.max_hosted_services = 0
        self.current_core_count = 0
        self.current_hosted_services = 0
        self.current_storage_accounts = 0
        self.max_virtual_network_sites = 0
        self.max_local_network_sites = 0
        self.max_dns_servers = 0


class AvailabilityResponse(WindowsAzureData):

    def __init__(self):
        self.result = False


class SubscriptionCertificates(WindowsAzureData):

    def __init__(self):
        self.subscription_certificates = _list_of(SubscriptionCertificate)

    def __iter__(self):
        return iter(self.subscription_certificates)

    def __len__(self):
        return len(self.subscription_certificates)

    def __getitem__(self, index):
        return self.subscription_certificates[index]


class SubscriptionCertificate(WindowsAzureData):

    def __init__(self):
        self.subscription_certificate_public_key = u''
        self.subscription_certificate_thumbprint = u''
        self.subscription_certificate_data = u''
        self.created = u''


class AzureHTTPRequest(object):

    def __init__(self):
        self.host = ''
        self.method = ''
        self.path = ''
        self.query = []      # list of (name, value)
        self.headers = {}    # list of (header name, header value)
        self.body = ''
        self.protocol_override = None


class AzureHTTPResponse(object):

    def __init__(self, status, message, headers, body):
        self.status = status
        self.message = message
        self.headers = headers
        self.body = body


"""
Helper classes and functions.
"""


class _Base64String(str):
    pass


class _list_of(list):

    """a list which carries with it the type that's expected to go in it.
    Used for deserializaion and construction of the lists"""

    def __init__(self, list_type, xml_element_name=None):
        self.list_type = list_type
        if xml_element_name is None:
            self.xml_element_name = list_type.__name__
        else:
            self.xml_element_name = xml_element_name
        super(_list_of, self).__init__()


class _scalar_list_of(list):

    """a list of scalar types which carries with it the type that's
    expected to go in it along with its xml element name.
    Used for deserializaion and construction of the lists"""

    def __init__(self, list_type, xml_element_name):
        self.list_type = list_type
        self.xml_element_name = xml_element_name
        super(_scalar_list_of, self).__init__()


class _dict_of(dict):

    """a dict which carries with it the xml element names for key,val.
    Used for deserializaion and construction of the lists"""

    def __init__(self, pair_xml_element_name, key_xml_element_name,
                 value_xml_element_name):
        self.pair_xml_element_name = pair_xml_element_name
        self.key_xml_element_name = key_xml_element_name
        self.value_xml_element_name = value_xml_element_name
        super(_dict_of, self).__init__()


class AzureNodeLocation(NodeLocation):

    # we can also have something in here for available services which is an
    # extra to the API with Azure

    def __init__(self, id, name, country, driver, available_services,
                 virtual_machine_role_sizes):
        super(AzureNodeLocation, self).__init__(id, name, country, driver)
        self.available_services = available_services
        self.virtual_machine_role_sizes = virtual_machine_role_sizes

    def __repr__(self):
        return (('<AzureNodeLocation: id=%s, name=%s, country=%s, '
                 'driver=%s services=%s virtualMachineRoleSizes=%s >')
                % (self.id, self.name, self.country,
                   self.driver.name, ','.join(self.available_services),
                   ','.join(self.virtual_machine_role_sizes)))


