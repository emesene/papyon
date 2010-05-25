# -*- coding: utf-8 -*-
#
# papyon - a python client library for Msn
#
# Copyright (C) 2007 Ali Sabil <asabil@gmail.com>
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

from papyon.msnp.message import MessageAcknowledgement
from papyon.msnp2p.transport.TLP import MessageChunk
from papyon.msnp2p.transport.base import BaseP2PTransport
from papyon.switchboard_manager import SwitchboardClient

import gobject
import struct
import logging

__all__ = ['SwitchboardP2PTransport']

logger = logging.getLogger('papyon.msnp2p.transport.switchboard')


class SwitchboardP2PTransport(BaseP2PTransport, SwitchboardClient):
    def __init__(self, client, switchboard, contacts, peer, peer_guid, transport_manager):
        self._peer = peer
        self._peer_guid = peer_guid
        SwitchboardClient.__init__(self, client, switchboard, contacts)
        BaseP2PTransport.__init__(self, transport_manager, "switchboard")

    def close(self):
        BaseP2PTransport.close(self)
        self._leave()

    @staticmethod
    def _can_handle_message(message, switchboard_client=None):
        content_type = message.content_type[0]
        return content_type == 'application/x-msnmsgrp2p'

    @staticmethod
    def handle_peer(client, peer, peer_guid, transport_manager):
        return SwitchboardP2PTransport(client, None, (peer,), peer, peer_guid,
            transport_manager)

    @staticmethod
    def handle_message(client, switchboard, message, transport_manager):
        guid = None
        peer = None
        if 'P2P-Src' in message.headers and ';' in message.headers['P2P-Src']:
            account, guid = message.headers['P2P-Src'].split(';', 1)
            guid = guid[1:-1]
            if account == client.profile.account:
                peer = client.profile
        if peer is None:
            peer = switchboard.participants.values()[0]
        return SwitchboardP2PTransport(client, switchboard, (), peer, guid,
            transport_manager)

    @property
    def peer(self):
        return self._peer

    @property
    def peer_guid(self):
        return self._peer_guid

    @property
    def rating(self):
        return 0

    @property
    def max_chunk_size(self):
        return 1250 # length of the chunk including the header but not the footer

    def _send_chunk(self, chunk):
        logger.debug(">>> %s" % repr(chunk))
        if self.version is 1:
            headers = {'P2P-Dest': self.peer.account}
        elif self.version is 2:
            headers = {'P2P-Src' : self._client.profile.account + ";{" +
                                   self._client.machine_guid + "}",
                       'P2P-Dest': self.peer.account + ";{" +
                                   self.peer_guid + "}"}
        content_type = 'application/x-msnmsgrp2p'
        body = str(chunk) + struct.pack('>L', chunk.application_id)
        self._send_message(content_type, body, headers,
                MessageAcknowledgement.MSNC, self._on_chunk_sent, (chunk,))

    def _on_message_received(self, message):
        version = 1
        # if destination contains a GUID, the protocol should be TLPv2
        if 'P2P-Dest' in message.headers and ';' in message.headers['P2P-Dest']:
            version = 2
            dest_guid = message.headers['P2P-Dest'].split(';', 1)[1][1:-1]
            if dest_guid != self._client.machine_guid:
                return # this chunk is not for us

        chunk = MessageChunk.parse(version, message.body[:-4])
        chunk.application_id = struct.unpack('>L', message.body[-4:])[0]
        logger.debug("<<< %s" % repr(chunk))
        self._on_chunk_received(chunk)

    def _on_contact_joined(self, contact):
        pass

    def _on_contact_left(self, contact):
        self.close()
