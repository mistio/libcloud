from libcloud.compute.base import Node, NodeDriver
from libcloud.common.clearvm import ClearVmConnection
from libcloud.compute.types import Provider, NodeState

import json


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

    def __init__(self, key=None, url=None,verify=True):
        """
        :param key: apikey
        :param uri: api endpoint
        """

        if not key:
            raise Exception("Api Key not specified")

        host = url

       # strip the prefix
        prefixes = ['http://', 'https://']
        for prefix in prefixes:
            if host.startswith(prefix):
                host = host.replace(prefix, '')
        host = host.split('/')[0]

        self.connectionCls.host = host
        super(ClearVmNodeDriver, self).__init__(key=key, uri=url)
        self.connection.host = host

    def list_nodes(self):
        """
        List clearvm nodes

        :rtype: ``list`` of :class:`ClearVmNode`
        """

        response = self.connection.request('/clearos/clearapi/v2/rest/host/get_all_host')
        nodes = [self._to_node(host)
                 for host in response.object['data']]
        return nodes


    def _to_node(self, data):
        extra_keys = ['model_name', 'serial_number', 'cpu_usages', 'ram', 'add_date',
                      'ram_usages', 'uuid', 'added_by', 'company_id', 'product_id']

        extra = {}
        private_ips = []
        private_ips.append(data['ipv4'])

        if data['status'] == 'Active':
            state = NodeState.RUNNING
        else:
            state = NodeState.STOPPED

        for key in extra_keys:
            if key in data:
                extra[key] = data[key]

        import ipdb; ipdb.set_trace();

        json_data = {"uuid": data['uuid']}
        response = self.connection.request('/clearos/clearapi/v2/rest/host/power_info',
                                            data=json.dumps(json_data), method='POST')
        power_info = self._get_power_info_dict(response.object['data'])
        node = Node(id=data['id'], name=data['model_name'], state=state,
                    private_ips=private_ips, public_ips=[], created_at=data['add_date'],
                    driver=self, extra=extra)
        return node


    def ex_start_node(self, node):
        data = {"uuid": node.extra['uuid']}
        res = self.connection.request('/clearos/clearapi/v2/rest/host/power/on',
                                      data=data, method='POST')
        return res.status in [httplib.OK, httplib.CREATED, httplib.ACCEPTED]

    def ex_stop_node(self, node):
        data = {"uuid": node.extra['uuid']}
        res = self.connection.request('/clearos/clearapi/v2/rest/host/power/off',
                                      data=data, method='POST')
        return res.status in [httplib.OK, httplib.CREATED, httplib.ACCEPTED]

    def ex_get_host(self, node):
        data = {"uuid": node.extra['uuid']}
        response = self.connection.request('/clearos/clearapi/v2/rest/host/get_host',
                                      data=data, method='POST')
        if 'data' in response.object:
            ret = {}
            ret['id'] = response.object['data']['id']
            ret['uuid'] = response.object['data']['uuid']
            ret['power_control_info'] = response.object['data']['power_control_info']
            ret['power_supply_info'] = response.object['data']['power_supply_info']

        return ret

    @staticmethod
    def _get_power_info_dict(data):
        import ipdb; ipdb.set_trace();
        power_info = {}
        power_info['MinConsumedWatts'] = data['power_control_info'][0]['PowerMetrics']['MinConsumedWatts']
        power_info['MaxConsumedWatts'] = data['power_control_info'][0]['PowerMetrics']['MaxConsumedWatts']
        power_info['AverageConsumedWatts'] = data['power_control_info'][0]['PowerMetrics']['AverageConsumedWatts']
        power_info['PowerCapacityWatts'] = data['power_control_info'][0]['PowerCapacityWatts']
        power_info['PowerConsumedWatts'] = data['power_control_info'][0]['PowerConsumedWatts']
        power_info['PowerConsumedWatts'] = data['power_control_info'][0]['PowerConsumedWatts']
        power_info['Health'] = data['power_supply_info'][0]['Status']['Health']
        #power_info['LastPowerOutputWatts'] = data['power_supply_info'][0]['Status']['Health']
