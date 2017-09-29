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
"""Module for resolving design references."""

import urllib.parse

import requests

from drydock_provisioner import error as errors


class DesignResolver(object):
    """Class for handling different design references to resolve them to a design document."""

    def __init__(self):
        self.scheme_handlers = {
            'http': self.resolve_reference_http,
            'file': self.resolve_reference_file,
            'https': self.resolve_reference_http,
            'deckhand+http': self.resolve_reference_deckhand,
        }

    def resolve_reference(self, design_ref):
        """Resolve a reference to a design document.

        Locate a schema handler based on the URI scheme of the design reference
        and use that handler to get the design document referenced.

        :param design_ref: A URI-formatted reference to a design document
        """
        try:
            design_uri = urllib.parse.urlparse(design_ref)

            handler = self.scheme_handlers.get(design_uri.scheme, None)

            if handler is None:
                raise errors.InvalidDesignReference(
                    "Invalid reference scheme %s: no handler." %
                    design_uri.scheme)
            else:
                return handler(design_uri)
        except ValueError:
            raise errors.InvalidDesignReference(
                "Cannot resolve design reference %s: unable to parse as valid URI."
                % design_ref)

    def resolve_reference_http(self, design_uri):
        """Retrieve design documents from http/https endpoints.

        Return a byte array of the design document. Support unsecured or
        basic auth

        :param design_uri: Tuple as returned by urllib.parse for the design reference
        """
        if design_uri.username is not None and design_uri.password is not None:
            response = requests.get(
                design_uri.geturl(),
                auth=(design_uri.username, design_uri.password),
                timeout=30)
        else:
            response = requests.get(design_uri.geturl(), timeout=30)

        return response.content

    def resolve_reference_file(self, design_uri):
        """Retrieve design documents from local file endpoints.

        Return a byte array of the design document.

        :param design_uri: Tuple as returned by urllib.parse for the design reference
        """
        if design_uri.path != '':
            f = open(design_uri.path, 'rb')
            doc = f.read()
            return doc

    def resolve_reference_deckhand(self, design_uri):
        """Retrieve design documents from Deckhand endpoints.

        Return a byte array of the design document. Assumes Keystone
        authentication required.

        :param design_uri: Tuple as returned by urllib.parse for the design reference
        """
        raise errors.InvalidDesignReference(
            "Deckhand references not currently supported.")
