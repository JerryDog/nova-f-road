增加冷迁移可指定主机，Resize限定本机

修改内容：
# nova-f-road\nova\api\openstack\compute\migrate_server.py line49
host = body["migrate"]["host"]
self.compute_api.resize(req.environ['nova.context'], instance, None, True, host)

# nova-f-road\nova\compute\api.py line2592
def resize(self, context, instance, flavor_id=None, clean_shutdown=True, destination_host_name=None,
               **extra_instance_updates):


# nova-f-road\nova\compute\api.py line2671
filter_properties = {'ignore_hosts': [],
                             'instance_host_name':instance['host'],
                             'destination_host_name':destination_host_name}

# nova-f-road\nova\conductor\tasks\migrate.py line62-73
注释原来的 host，node
node = self.filter_properties['destination_host_name'] if self.filter_properties['destination_host_name'] \
            else self.filter_properties['instance_host_name']
host = self.filter_properties['destination_host_name'] if self.filter_properties['destination_host_name'] \
    else self.filter_properties['instance_host_name']