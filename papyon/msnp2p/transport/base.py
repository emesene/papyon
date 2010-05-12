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

from papyon.msnp2p.transport.TLP import ControlBlob

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
            }

    def __init__(self, transport_manager, name):
        gobject.GObject.__init__(self)
        self._transport_manager = weakref.proxy(transport_manager)
        self._client = transport_manager._client
        self._name = name
        self._source = None

        self._local_chunk_id = random.randint(1000, MAX_INT32)
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

    def send(self, blob, callback=None, errback=None):
        self._queue_lock.acquire()
        if blob.is_control_blob():
            self._control_blob_queue.append((blob, callback, errback))
        else:
            self._data_blob_queue.append((blob, callback, errback))
        self._queue_lock.release()

        if self._source is None:
            self._source = gobject.timeout_add(200, self._process_send_queues)
            self._process_send_queues()

    def cleanup(self, session_id):
        # remove this session's blobs from the data queue
        # don't clean up the control queue as we still want the BYE to be sent
        self._queue_lock.acquire()
        canceled_blobs = []
        for blob in self._data_blob_queue:
            if blob[0].session_id == session_id:
                canceled_blobs.append(blob)
        for blob in canceled_blobs:
            self._data_blob_queue.remove(blob)
        self._queue_lock.release()

    def close(self):
        self._transport_manager._unregister_transport(self)

    def _send_chunk(self, chunk):
        raise NotImplementedError

    # Helper methods
    def _reset(self):
        self._queue_lock.acquire()
        self._control_blob_queue = []
        self._data_blob_queue = []
        self._pending_blob = {} # ack_id : (blob, callback, errback)
        self._pending_ack = set()
        self._queue_lock.release()

    def _add_pending_ack(self, ack_id):
        self._pending_ack.add(ack_id)

    def _del_pending_ack(self, ack_id):
        self._pending_ack.discard(ack_id)

    def _add_pending_blob(self, ack_id, blob, callback, errback):
        if blob.is_data_blob():
            self._pending_blob[ack_id] = (blob, callback, errback)
        elif callback:
            callback[0](*callback[1:])

    def _del_pending_blob(self, ack_id):
        if not ack_id in self._pending_blob:
            return
        blob, callback, errback = self._pending_blob[ack_id]
        del self._pending_blob[ack_id]
        if callback:
            callback[0](*callback[1:])

    def _on_chunk_received(self, chunk):
        if chunk.require_ack():
            ack_chunk = chunk.create_ack_chunk()
            ack = ControlBlob(ack_chunk)
            self.send(ack)

        if chunk.is_ack_chunk() or chunk.is_nak_chunk():
            self._del_pending_ack(chunk.acked_id)
            self._del_pending_blob(chunk.acked_id)

        #FIXME: handle all the other flags (NAK...)

        if not chunk.is_control_chunk():
            self.emit("chunk-received", chunk)

        self._process_send_queues()

    def _on_chunk_sent(self, chunk):
        self.emit("chunk-sent", chunk)
        if chunk in self._pending_blob:
            blob, callback, errback = self._pending_blob.pop(chunk)
            if callback:
                callback[0](*callback[1:])
        self._process_send_queues()

    def _process_send_queues(self):
        if not self._queue_lock.acquire(False):
            return True
        if len(self._control_blob_queue) > 0:
            queue = self._control_blob_queue
        elif len(self._data_blob_queue) > 0:
            queue = self._data_blob_queue
        else:
            self._queue_lock.release()
            if self._source is not None:
                gobject.source_remove(self._source)
                self._source = None
            return False

        blob, callback, errback = queue[0]
        chunk = blob.get_chunk(self.max_chunk_size)
        chunk.id = self._local_chunk_id
        self._local_chunk_id = chunk.next_id

        if blob.is_complete():
            queue.pop(0)
            self._add_pending_blob(chunk.ack_id, blob, callback, errback)
        self._queue_lock.release()

        if chunk.require_ack() :
            self._add_pending_ack(chunk.ack_id)
        self._send_chunk(chunk)
        return True

gobject.type_register(BaseP2PTransport)
