from libcloud.compute.base import Node, NodeDriver
from libcloud.common.clearvm import ClearVmConnection
from libcloud.compute.types import Provider, NodeState


__all__ = [
    "ClearVmNodeDriver"
]

class ClearVmNodeDriver(NodeDriver):
    """
    Base ClearVm node driver.
    A `node` can be either a host or a guest
    """

    connectionCls = ClearVmConnection
    type = Provider.CLEARVM
    name = 'ClearVm'
    website = 'https://www.clearvm.com'

    # TODO: map describing available states of nodes
    NODE_STATE_MAP = {'Active': NodeState.RUNNING,
                      'off': NodeState.OFF}

    def __init__(self, key=None, uri=None,verify=True):
        """
        :param key: apikey
        :param uri: api endpoint
        """

        self.connectionCls.host = uri
        super(ClearVmNodeDriver, self).__init__(key=key, uri=uri)


    def list_nodes(self):
        """
        List clearvm nodes

        :rtype: ``list`` of :class:`ClearVmNode`
        """
        # TODO
        response = self.connection.request('http://xsdemo.com/clearos/clearapi/v2/rest/host/get_all_host')
        nodes = [self._to_node(host)
                 for host in response.object['data']]
        return nodes


    def _to_node(self, data):
        extra_keys = ['model_name', 'serial_number', 'cpu_usages', 'ram',
                      'ram_usages', 'uuid', 'added_by', 'company_id', 'product_id']

        private_ips = []
        private_ips.append(data['ipv4'])

        state = NODE_STATE_MAP.get(data['status'])

        for key in extra_keys:
            if key in data:
                extra[key] = data[key]

        node = Node(id=data['id'], name=data['host_name'], state=state,
                    private_ips=private_ips, created_at=data['add_date'],
                    driver=self, extra=extra)
        return node

    def ex_start_node(self, node):
        params = {"uuid": node.extra['uuid']}
        res = self.connection.request('/host/power/on',
                                      params=params, method='POST')
        return res.status in [httplib.OK, httplib.CREATED, httplib.ACCEPTED]

    def ex_stop_node(self, node):
        params = {"uuid": node.extra['uuid']}
        res = self.connection.request('/host/power/off',
                                      params=params, method='POST')
        return res.status in [httplib.OK, httplib.CREATED, httplib.ACCEPTED]

    def ex_get_host(self, node):
        params = {"uuid": node.extra['uuid']}
        response = self.connection.request('/host/get_host',
                                      params=params, method='POST')
        if 'data' in response.object:
            ret = {}
            ret['id'] = response.object['data']['id']
            ret['uuid'] = response.object['data']['uuid']
            ret['power_control_info'] = response.object['data']['power_control_info']
            ret['power_supply_info'] = response.object['data']['power_supply_info']

        return ret
