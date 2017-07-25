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

from oslo_config import cfg
from oslo_policy import policy

class DrydockPolicy(object):
    """
    Initialize policy defaults
    """

    # Base Policy
    base_rules = [
        policy.RuleDefault('admin_required', 'role:admin or is_admin:1', description='Actions requiring admin authority'),
    ]

    # Orchestrator Policy
    task_rules = [
        policy.RuleDefault('physical_provisioner:read_task', 'role:operator', description='Get task status'),
        policy.RuleDefault('physical_provisioner:validate_design', 'role:operator', description='Create validate_design task'),
        policy.RuleDefault('physical_provisioner:verify_site', 'role:operator', description='Create verify_site task'),
        policy.RuleDefault('physical_provisioner:prepare_site', 'role:operator', description='Create prepare_site task'),
        policy.RuleDefault('physical_provisioner:verify_node', 'role:operator', description='Create verify_node task'),
        policy.RuleDefault('physical_provisioner:prepare_node', 'role:operator', description='Create prepare_node task'),
        policy.RuleDefault('physical_provisioner:deploy_node', 'role:operator', description='Create deploy_node task'),
        policy.RuleDefault('physical_provisioner:destroy_node', 'role:operator', description='Create destroy_node task'),

    ]

    # Data Management Policy
    data_rules = [
        policy.RuleDefault('physical_provisioner:read_data', 'role:user', description='Read loaded design data'),
        policy.RuleDefault('physical_provisioner:ingest_data', 'role:operator', description='Load design data'),
    ]

    def __init__(self):
        self.enforcer = policy.Enforcer(cfg.CONF)

    def register_policy(self):
        self.enforcer.register_defaults(DrydockPolicy.base_rules)
        self.enforcer.register_defaults(DrydockPolicy.task_rules)
        self.enforcer.register_defaults(DrydockPolicy.data_rules)
        self.enforcer.load_rules()

    def authorize(self, action, ctx):
        target = {'project_id': ctx.project_id, 'user_id': ctx.user_id}
        return self.enforcer.authorize(action, target, ctx.to_policy_view())


def list_policies():
    default_policy = []
    default_policy.extend(DrydockPolicy.base_rules)
    default_policy.extend(DrydockPolicy.task_rules)
    default_policy.extend(DrydockPolicy.data_rules)

    return default_policy
