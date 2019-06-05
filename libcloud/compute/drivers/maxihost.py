from libcloud.compute.base import Node, NodeDriver, NodeLocation, NodeSize, NodeImage
from libcloud.common.maxihost import MaxihostConnection
from libcloud.compute.types import Provider, NodeState

import json


__all__ = [
    "MaxihostNodeDriver"
]

class MaxihostNodeDriver(NodeDriver):
    """
    Base Maxihost node driver.
    """

    connectionCls = MaxihostConnection
    type = Provider.MAXIHOST
    name = 'Maxihost'


    def list_nodes(self):
        """
        List nodes

        :rtype: ``list`` of :class:`MaxihostNode`
        """
        response = self.connection.request('/devices')
        nodes = [self._to_node(host)
                 for host in response.object['devices']]
        return nodes


    def _to_node(self, data):
        extra = {}
        #private_ips = []
        #private_ips.append(data['ipv4'])

        if data['power_status']:
            state = NodeState.RUNNING
        else:
            state = NodeState.STOPPED

        for key in data:
            extra[key] = data[key]

        # TODO: Fix public and private ips
        node = Node(id=data['id'], name=data['description'], state=state,
                    private_ips=[], public_ips=[],
                    driver=self, extra=extra)
        return node
        
    def list_locations(self, available=True):
        """
        List locations

        If available is True, show only locations which are available
        """
        locations = []
        data = self.connection.request('/regions')
        for location in data.object['regions']:
            if available:
                if location.get('available'):
                    locations.append(self._to_location(location))
            else:
                locations.append(self._to_location(location))
        return locations
    
    def _to_location(self, data):
        extra = {'features': data.get('features', [])}
        country = data.get('location').get('country', '')
        return NodeLocation(id=data['slug'], name=data['name'], country=None,
                            extra=extra, driver=self)

    def list_sizes(self):
        """
        List sizes
        """
        sizes = []
        data = self.connection.request('/plans')
        for size in data.object['servers']:
                sizes.append(self._to_size(size))
        return sizes

    def _to_size(self, data):
        extra = {'vcpus': data['specs']['cpus']['count'],
                 'regions': data['regions'],
                 'pricing': data['pricing']}
        return NodeSize(id=data['id'], name=data['slug'], ram=data['specs']['memory']['total'],
                        disk=None, bandwidth=None,
                        price=data['pricing'], driver=self, extra=extra)

    def list_images(self):
        """
        List images
        """
        images = []
        data = self.connection.request('/plans/operating-systems')
        import ipdb;ipdb.set_trace()
        for image in data.object['operating-systems']:
                images.append(self._to_image(image))
        return images

    def _to_image(self, data):
        extra = {'operating_system': data['operating_system'],
                 'slug': data['slug'],
                 'distro': data['distro'],
                 'version': data['version'],
                 'pricing': data['pricing']}
        return NodeImage(id=data['id'], name=data['name'], driver=self,
                         extra=extra)