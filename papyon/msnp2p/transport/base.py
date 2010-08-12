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

from papyon.msnp2p.transport.TLP import MessageBlob

import gobject
import logging
import random
import threading
import weakref

__all__ = ['BaseP2PTransport']

logger = logging.getLogger('papyon.msnp2p.transport')


MAX_INT32 = 2147483647

class BaseP2PTransport(gobject.GObject):
    __gsignals__ = {
            "chunk-received": (gobject.SIGNAL_RUN_FIRST,
                gobject.TYPE_NONE,
                (object,)),

            "chunk-sent": (gobject.SIGNAL_RUN_FIRST,
                gobject.TYPE_NONE,
                (object,)),

            "blob-received": (gobject.SIGNAL_RUN_FIRST,
                gobject.TYPE_NONE,
                (object,)),

            "blob-sent": (gobject.SIGNAL_RUN_FIRST,
                gobject.TYPE_NONE,
                (object,)),
            }

    def __init__(self, transport_manager, name):
        gobject.GObject.__init__(self)
        self._transport_manager = weakref.proxy(transport_manager)
        self._client = transport_manager._client
        self._name = name
        self._source = None

        self._local_chunk_id = None
        self._remote_chunk_id = None

        self._transport_manager._register_transport(self)
        self._queue_lock = threading.Lock()
        self._reset()

    @property
    def name(self):
        return self._name

    @property
    def peer(self):
        raise NotImplementedError

    @property
    def rating(self):
        raise NotImplementedError

    @property
    def max_chunk_size(self):
        raise NotImplementedError

    @property
    def version(self):
        if self._client.profile.client_id.supports_p2pv2 and \
                self.peer.client_capabilities.supports_p2pv2:
            return 2
        else:
            return 1

    def can_send(self, peer, peer_guid, blob, bootstrap=False):
        raise NotImplementedError

    def send(self, peer, peer_guid, blob):
        self._queue_lock.acquire()
        self._data_blob_queue.append((peer, peer_guid, blob))
        self._queue_lock.release()

        if self._source is None:
            self._source = gobject.timeout_add(200, self._process_send_queue)
        self._process_send_queue()

    def cleanup(self, session_id):
        # remove this session's blobs from the data queue
        self._queue_lock.acquire()
        canceled_blobs = []
        for blob in self._data_blob_queue:
            if blob[2].session_id == session_id:
                canceled_blobs.append(blob)
        for blob in canceled_blobs:
            self._data_blob_queue.remove(blob)
        self._queue_lock.release()

    def close(self):
        self._transport_manager._unregister_transport(self)

    def _send_chunk(self, peer, peer_guid, chunk):
        raise NotImplementedError

    # Helper methods ---------------------------------------------------------

    def _reset(self):
        self._queue_lock.acquire()
        self._first = True
        self._data_blob_queue = []
        self._pending_blob = {} # ack_id : (blob, callback, errback)
        self._pending_ack = set()
        self._signaling_blobs = {} # blob_id : blob
        self._queue_lock.release()

    def _add_pending_ack(self, ack_id):
        self._pending_ack.add(ack_id)

    def _del_pending_ack(self, ack_id):
        self._pending_ack.discard(ack_id)

    def _add_pending_blob(self, ack_id, blob):
        if self.version == 1:
            self._pending_blob[ack_id] = blob
        else:
            self.emit("blob-sent", blob)

    def _del_pending_blob(self, ack_id):
        if not ack_id in self._pending_blob:
            return
        blob = self._pending_blob.pop(ack_id)
        self.emit("blob-sent", blob)

    def _on_chunk_received(self, peer, peer_guid, chunk):
        if chunk.is_data_preparation_chunk():
            return

        if chunk.require_ack():
            ack_chunk = chunk.create_ack_chunk()
            self.__send_chunk(peer, peer_guid, ack_chunk)

        if chunk.is_ack_chunk() or chunk.is_nak_chunk():
            self._del_pending_ack(chunk.acked_id)
            self._del_pending_blob(chunk.acked_id)

        #FIXME: handle all the other flags (NAK...)

        if not chunk.is_control_chunk():
            if chunk.is_signaling_chunk(): # signaling chunk
                self._on_signaling_chunk_received(chunk)
            else: # data chunk (buffered by the transport manager)
                self.emit("chunk-received", chunk)

        self._process_send_queue()

    def _on_signaling_chunk_received(self, chunk):
        blob_id = chunk.blob_id
        if blob_id in self._signaling_blobs:
            blob = self._signaling_blobs[blob_id]
        else:
            # create an in-memory blob
            blob = MessageBlob(chunk.application_id, "",
                chunk.blob_size, chunk.session_id, blob_id)
            self._signaling_blobs[blob_id] = blob

        blob.append_chunk(chunk)
        if blob.is_complete():
            self.emit("blob-received", blob)
            del self._signaling_blobs[blob_id]

    def _on_chunk_sent(self, chunk):
        self.emit("chunk-sent", chunk)
        self._process_send_queue()

    def _process_send_queue(self):
        if not self._queue_lock.acquire(False):
            return True
        if len(self._data_blob_queue) == 0:
            self._queue_lock.release()
            if self._source is not None:
                gobject.source_remove(self._source)
                self._source = None
            return False

        sync = self._first
        self._first = False
        (peer, peer_guid, blob) = self._data_blob_queue[0]
        chunk = blob.get_chunk(self.version, self.max_chunk_size, sync)
        self.__send_chunk(peer, peer_guid, chunk)

        if blob.is_complete():
            self._data_blob_queue.pop(0)
            self._add_pending_blob(chunk.ack_id, blob)
        self._queue_lock.release()
        return True

    def __send_chunk(self, peer, peer_guid, chunk):
        # add local identifier to chunk
        if self._local_chunk_id is None:
            self._local_chunk_id = random.randint(1000, MAX_INT32)
        chunk.id = self._local_chunk_id
        self._local_chunk_id = chunk.next_id

        if chunk.require_ack() :
            self._add_pending_ack(chunk.ack_id)

        self._send_chunk(peer, peer_guid, chunk)

gobject.type_register(BaseP2PTransport)
