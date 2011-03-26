# -*- coding: utf-8 -*-
#
# papyon - a python client library for Msn
#
# Copyright (C) 2010 Collabora Ltd.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

from papyon.msnp2p.transport.base import BaseP2PTransport

import gobject
import logging

__all__ = ['DefaultP2PTransport']

logger = logging.getLogger('papyon.msnp2p.transport.default')


class DefaultP2PTransport(BaseP2PTransport):

    def __init__(self, client, peer, peer_guid, transport_manager):
        self._peer = peer
        self._peer_guid = peer_guid
        BaseP2PTransport.__init__(self, transport_manager)

    @staticmethod
    def handle_peer(client, peer, peer_guid, transport_manager, **kwargs):
        return DefaultP2PTransport(client, peer, peer_guid, transport_manager)

    @property
    def name(self):
        return "default"

    @property
    def protocol(self):
        return "None"

    @property
    def peer(self):
        return self._peer

    @property
    def peer_guid(self):
        return self._peer_guid

    @property
    def connected(self):
        return True

    @property
    def rating(self):
        return 0

    @property
    def max_chunk_size(self):
        return 0

    def can_send(self, peer, peer_guid, blob):
        return (self._peer == peer and self._peer_guid == peer_guid)

    def _ready_to_send(self):
        return False

    def _send_chunk(self, peer, peer_guid, chunk):
        pass

    def __repr__(self):
        return '<DefaultP2PTransport peer="%s" guid="%s">' % \
                (self.peer.account, self.peer_guid)
