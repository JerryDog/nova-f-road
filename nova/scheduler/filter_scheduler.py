# Copyright (c) 2011 OpenStack Foundation
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
The FilterScheduler is for creating instances locally.
You can customize this scheduler by specifying your own Host Filters and
Weighing Functions.
"""

import random

from oslo_log import log as logging
from six.moves import range

import nova.conf
from nova import exception
from nova.i18n import _
from nova import rpc
from nova.scheduler import driver
from nova.scheduler import scheduler_options


CONF = nova.conf.CONF
LOG = logging.getLogger(__name__)


class FilterScheduler(driver.Scheduler):
    """Scheduler that can be used for filtering and weighing."""
    def __init__(self, *args, **kwargs):
        super(FilterScheduler, self).__init__(*args, **kwargs)
        self.options = scheduler_options.SchedulerOptions()
        self.notifier = rpc.get_notifier('scheduler')

    def select_destinations(self, context, spec_obj):
        """Selects a filtered set of hosts and nodes."""
        self.notifier.info(
            context, 'scheduler.select_destinations.start',
            dict(request_spec=spec_obj.to_legacy_request_spec_dict()))

        num_instances = spec_obj.num_instances
        selected_hosts = self._schedule(context, spec_obj)

        # Couldn't fulfill the request_spec
        if len(selected_hosts) < num_instances:
            # NOTE(Rui Chen): If multiple creates failed, set the updated time
            # of selected HostState to None so that these HostStates are
            # refreshed according to database in next schedule, and release
            # the resource consumed by instance in the process of selecting
            # host.
            for host in selected_hosts:
                host.obj.updated = None

            # Log the details but don't put those into the reason since
            # we don't want to give away too much information about our
            # actual environment.
            LOG.debug('There are %(hosts)d hosts available but '
                      '%(num_instances)d instances requested to build.',
                      {'hosts': len(selected_hosts),
                       'num_instances': num_instances})

            reason = _('There are not enough hosts available.')
            raise exception.NoValidHost(reason=reason)

        dests = [dict(host=host.obj.host, nodename=host.obj.nodename,
                      limits=host.obj.limits) for host in selected_hosts]

        self.notifier.info(
            context, 'scheduler.select_destinations.end',
            dict(request_spec=spec_obj.to_legacy_request_spec_dict()))
        return dests

    def _get_configuration_options(self):
        """Fetch options dictionary. Broken out for testing."""
        return self.options.get_configuration()

    def _schedule(self, context, spec_obj):
        """Returns a list of hosts that meet the required specs,
        ordered by their fitness.
        """
        elevated = context.elevated()

        config_options = self._get_configuration_options()

        # Find our local list of acceptable hosts by repeatedly
        # filtering and weighing our options. Each time we choose a
        # host, we virtually consume resources on it so subsequent
        # selections can adjust accordingly.

        # Note: remember, we are using an iterator here. So only
        # traverse this list once. This can bite you if the hosts
        # are being scanned in a filter or weighing function.
        hosts = self._get_all_host_states(elevated)
        selected_hosts = []
        num_instances = spec_obj.num_instances
        # NOTE(sbauza): Adding one field for any out-of-tree need
        spec_obj.config_options = config_options
        for num in range(num_instances):
            # Filter local hosts based on requirements ...
            hosts = self.host_manager.get_filtered_hosts(hosts,
                    spec_obj, index=num)
            if not hosts:
                # Can't get any more locally.
                break

            LOG.info("Filtered %(hosts)s", {'hosts': hosts})

            weighed_hosts = self.host_manager.get_weighed_hosts(hosts,
                    spec_obj)

            LOG.info("Weighed %(hosts)s", {'hosts': weighed_hosts})

            scheduler_host_subset_size = max(1,
                                             CONF.scheduler_host_subset_size)
            if scheduler_host_subset_size < len(weighed_hosts):


                weighed_hosts = weighed_hosts[0:scheduler_host_subset_size]
            #chosen_host = random.choice(weighed_hosts)




            chosen_host = {}

            # add by jiahua at 2016-07-27
            filter_properties = spec_obj.to_legacy_filter_properties_dict()
            LOG.info('FFFFFFF filter_properties: %s' % filter_properties)
            if filter_properties.has_key('destination_host_name') and filter_properties['destination_host_name']:
                destinaton_host = filter_properties['destination_host_name']
                for single_host in weighed_hosts:
                    if single_host.obj.host == destinaton_host:
                        chosen_host = single_host
                        break
            elif filter_properties.has_key('instance_host_name') and filter_properties['instance_host_name']:
                instance_host_name = filter_properties['instance_host_name']
                for single_host in weighed_hosts:
                    if single_host.obj.host == instance_host_name:
                        chosen_host = single_host
                        LOG.debug(_("--------------------resize_host_name:%s") % chosen_host.obj.host)
                        break
            if not chosen_host:
                chosen_host = random.choice(weighed_hosts[0:scheduler_host_subset_size])

            selected_hosts.append(chosen_host)
            LOG.info("Selected host: %(host)s", {'host': selected_hosts})
            # Now consume the resources so the filter/weights
            # will change for the next instance.
            chosen_host.obj.consume_from_request(spec_obj)
            if spec_obj.instance_group is not None:
                spec_obj.instance_group.hosts.append(chosen_host.obj.host)
                # hosts has to be not part of the updates when saving
                spec_obj.instance_group.obj_reset_changes(['hosts'])
        return selected_hosts

    def _get_all_host_states(self, context):
        """Template method, so a subclass can implement caching."""
        return self.host_manager.get_all_host_states(context)
