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

import logging
import uuid
import re

import falcon

from oslo_config import cfg

class AuthMiddleware(object):

    def __init__(self):
        self.logger = logging.getLogger('drydock')

    # Authentication
    def process_request(self, req, resp):
        ctx = req.context

        for k, v in req.headers.items():
            self.logger.debug("Request with header %s: %s" % (k, v))

        auth_status = req.get_header('X-IDENTITY-STATUS')

        if auth_status == 'Confirmed':
            # Process account and roles
            ctx.authenticated = True
            ctx.user = req.get_header('X-USER-NAME')
            ctx.project = req.get_header('X-PROJECT-NAME')
            ctx.domain = req.get_header('X-PROJECT-DOMAIN-NAME')
            ctx.add_roles(req.get_header('X-ROLES').split(','))
            self.logger.debug('Request from authenticated user %s with roles %s' % (ctx.user, ','.join(ctx.roles)))
        else:
            ctx.authenticated = False


    # Authorization
    def process_resource(self, req, resp, resource, params):
        ctx = req.context

        if not resource.authorize_roles(ctx.roles):
            raise falcon.HTTPUnauthorized('Authentication required',
                                          ('This resource requires an authorized role.'))

    # Return the username associated with an authenticated token or None
    def validate_token(self, token):
        if token == '42':
            return 'scott'
        elif token == 'bigboss':
            return 'admin'
        else:
            return None

    # Return the list of roles assigned to the username
    # Roles need to be an enum
    def role_list(self, username):
        if username == 'scott':
            return ['user']
        elif username == 'admin':
            return ['user', 'admin']

class ContextMiddleware(object):

    def process_request(self, req, resp):
        ctx = req.context

        requested_logging = req.get_header('X-Log-Level')

        if (cfg.CONF.logging.log_level == 'DEBUG' or
           (requested_logging == 'DEBUG' and 'admin' in ctx.roles)):
            ctx.set_log_level('DEBUG')
        elif requested_logging == 'INFO':
            ctx.set_log_level('INFO')

        ext_marker = req.get_header('X-Context-Marker')
        ctx.set_external_marker(ext_marker if ext_marker is not None else '')

class LoggingMiddleware(object):

    def __init__(self):
        self.logger = logging.getLogger(cfg.CONF.logging.control_logger_name)

    def process_response(self, req, resp, resource, req_succeeded):
        ctx = req.context
        extra = {
            'user': ctx.user,
            'req_id': ctx.request_id,
            'external_ctx': ctx.external_marker,
        }
        resp.append_header('X-Drydock-Req', ctx.request_id)
        self.logger.info("%s - %s" % (req.uri, resp.status), extra=extra)
