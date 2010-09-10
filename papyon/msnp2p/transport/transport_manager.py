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

from papyon.msnp2p.transport.switchboard import *
from papyon.msnp2p.transport.notification import *
from papyon.msnp2p.transport.TLP import MessageBlob

import gobject
import struct
import logging
import os

__all__ = ['P2PTransportManager']

logger = logging.getLogger('papyon.msnp2p.transport')


class P2PTransportManager(gobject.GObject):
    __gsignals__ = {
            "blob-received" : (gobject.SIGNAL_RUN_FIRST,
                gobject.TYPE_NONE,
                (object,)),

            "blob-sent" : (gobject.SIGNAL_RUN_FIRST,
                gobject.TYPE_NONE,
                (object,)),

            "chunk-transferred" : (gobject.SIGNAL_RUN_FIRST,
                gobject.TYPE_NONE,
                (object,)),
    }

    def __init__(self, client):
        gobject.GObject.__init__(self)

        self._client = client
        switchboard_manager = self._client._switchboard_manager
        switchboard_manager.register_handler(SwitchboardP2PTransport, self)
        self._default_transport = lambda peer, peer_guid : \
            SwitchboardP2PTransport.handle_peer(client, peer, peer_guid, self)
        self._transports = set()
        self._transport_signals = {}
        self._data_blobs = {} # session_id => blob
        self._blacklist = set() # blacklist of session_id
        uun_transport = NotificationP2PTransport(client, self)

    def _register_transport(self, transport):
        logger.info("Registering transport %s" % repr(transport))
        assert transport not in self._transports, "Trying to register transport twice"
        self._transports.add(transport)
        signals = []
        signals.append(transport.connect("chunk-received",
            self._on_chunk_received))
        signals.append(transport.connect("chunk-sent",
            self._on_chunk_sent))
        signals.append(transport.connect("blob-received",
            self._on_blob_received))
        signals.append(transport.connect("blob-sent",
            self._on_blob_sent))
        self._transport_signals[transport] = signals

    def _unregister_transport(self, transport):
        if transport not in self._transports:
            return
        logger.info("Unregistering transport %s" % repr(transport))
        self._transports.discard(transport)
        signals = self._transport_signals.pop(transport, [])
        for signal in signals:
            transport.disconnect(signal)

    def _get_transport(self, peer, peer_guid, blob):
        for transport in self._transports:
            if transport.can_send(peer, peer_guid, blob):
                return transport
        return self._default_transport(peer, peer_guid)

    def _on_chunk_received(self, transport, chunk):
        self.emit("chunk-transferred", chunk)
        session_id = chunk.session_id
        blob_id = chunk.blob_id

        if session_id in self._blacklist:
            return

        if session_id in self._data_blobs:
            blob = self._data_blobs[session_id]
            if blob.transferred == 0:
                blob.id = chunk.blob_id
        else:
            # create an in-memory blob
            blob = MessageBlob(chunk.application_id, "",
                    chunk.blob_size, session_id, chunk.blob_id)
            self._data_blobs[session_id] = blob

        blob.append_chunk(chunk)
        if blob.is_complete():
            del self._data_blobs[session_id]
            self.emit("blob-received", blob)

    def _on_chunk_sent(self, transport, chunk):
        self.emit("chunk-transferred", chunk)

    def _on_blob_received(self, transport, blob):
        self.emit("blob-received", blob)

    def _on_blob_sent(self, transport, blob):
        self.emit("blob-sent", blob)

    def send_slp_message(self, peer, peer_guid, application_id, message):
        self.send_data(peer, peer_guid, application_id, 0, str(message))

    def send_data(self, peer, peer_guid, application_id, session_id, data):
        blob = MessageBlob(application_id, data, None, session_id, None)
        transport = self._get_transport(peer, peer_guid, blob)
        transport.send(peer, peer_guid, blob)

    def register_data_buffer(self, session_id, buffer, size):
        if session_id in self._data_blobs:
            logger.warning("registering already registered blob "\
                    "with session_id=" + str(session_id))
            return
        blob = MessageBlob(0, buffer, size, session_id)
        self._data_blobs[session_id] = blob

    def cleanup(self, session_id):
        if session_id in self._data_blobs:
            del self._data_blobs[session_id]
        for transport in self._transports:
            transport.cleanup(session_id)

    def add_to_blacklist(self, session_id):
        # ignore data chunks received for this session_id:
        # we want to ignore chunks received shortly after closing a session
        self._blacklist.add(session_id)

    def remove_from_blacklist(self, session_id):
        self._blacklist.discard(session_id)

gobject.type_register(P2PTransportManager)
