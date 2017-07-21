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
import logging
import functools

from oslo_config import cfg
from oslo_policy import policy

# Global reference to a instantiated DrydockPolicy. Will be initialized by drydock.py
policy_engine = None

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
        policy.DocumentedRuleDefault('physical_provisioner:read_task', 'role:admin', 'Get task status',
                                     [{'path': '/api/v1.0/tasks', 'method': 'GET'},
                                      {'path': '/api/v1.0/tasks/{task_id}', 'method': 'GET'}]),
        policy.DocumentedRuleDefault('physical_provisioner:validate_design', 'role:admin', 'Create validate_design task',
                                     [{'path': '/api/v1.0/tasks', 'method': 'POST'}]),
        policy.DocumentedRuleDefault('physical_provisioner:verify_site', 'role:admin', 'Create verify_site task',
                                     [{'path': '/api/v1.0/tasks', 'method': 'POST'}]),
        policy.DocumentedRuleDefault('physical_provisioner:prepare_site', 'role:admin', 'Create prepare_site task',
                                     [{'path': '/api/v1.0/tasks', 'method': 'POST'}]),
        policy.DocumentedRuleDefault('physical_provisioner:verify_node', 'role:admin', 'Create verify_node task',
                                     [{'path': '/api/v1.0/tasks', 'method': 'POST'}]),
        policy.DocumentedRuleDefault('physical_provisioner:prepare_node', 'role:admin', 'Create prepare_node task',
                                     [{'path': '/api/v1.0/tasks', 'method': 'POST'}]),
        policy.DocumentedRuleDefault('physical_provisioner:deploy_node', 'role:admin', 'Create deploy_node task',
                                     [{'path': '/api/v1.0/tasks', 'method': 'POST'}]),
        policy.DocumentedRuleDefault('physical_provisioner:destroy_node', 'role:admin', 'Create destroy_node task',
                                     [{'path': '/api/v1.0/tasks', 'method': 'POST'}]),

    ]

    # Data Management Policy
    data_rules = [
        policy.DocumentedRuleDefault('physical_provisioner:read_data', 'role:admin', 'Read loaded design data',
                                     [{'path': '/api/v1.0/designs', 'method': 'GET'},
                                      {'path': '/api/v1.0/designs/{design_id}', 'method': 'GET'}]),
        policy.DocumentedRuleDefault('physical_provisioner:ingest_data', 'role:admin', 'Load design data',
                                     [{'path': '/api/v1.0/designs', 'method': 'POST'},
                                      {'path': '/api/v1.0/designs/{design_id}/parts', 'method': 'POST'}])
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

class ApiEnforcer(object):
    """
    A decorator class for enforcing RBAC policies
    """

    def __init__(self, action):
        self.action = action
        self.logger = logging.getLogger('drydock.policy')

    def __call__(self, f):
        @functools.wraps(f)
        def secure_handler(slf, req, resp, *args):
            ctx = req.context

            policy_engine = ctx.policy_engine

            self.logger.debug("Enforcing policy %s on request %s" % (self.action, ctx.request_id))

            if policy_engine is not None and policy_engine.authorize(self.action, ctx):
                return f(slf, req, resp, *args)
            else:
                if ctx.authenticated:
                    slf.info(ctx, "Error - Forbidden access - action: %s" % self.action)
                    slf.return_error(resp, falcon.HTTP_403, message="Forbidden", retry=False)
                else:
                    slf.info(ctx, "Error - Unauthenticated access")
                    slf.return_error(resp, falcon.HTTP_401, message="Unauthenticated", retry=False)
        return secure_handler

def list_policies():
    default_policy = []
    default_policy.extend(DrydockPolicy.base_rules)
    default_policy.extend(DrydockPolicy.task_rules)
    default_policy.extend(DrydockPolicy.data_rules)

    return default_policy
