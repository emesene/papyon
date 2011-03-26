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

import socket

class NATTraversal(object):

    def __init__(self):
        pass

    def _map_port(self):
        self._request_echo_server((self._on_echo_server_answered,),
                (self._on_echo_server_failed,))

    def _request_echo_server(self, callback, errback):
        transport = TCPClient("64.4.35.253", 7001)
        transport.connect("notify::status", self._on_echo_transport_status_changed)
        transport.connect("error", self._on_echo_transport_error)
        transport.connect("received", self._on_echo_transport_received)
        self._echo_transports[transport] = ([], callback, errback)
        transport.open()

    def _listen(self, local_ip, local_port):
        s = socket.socket()
        s.setblocking(False)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        s.bind(("", local_port))
        s.listen(1)
        channel = gobject.IOChannel(s.fileno())
        channel.set_flags(channel.get_flags() | gobject.IO_FLAG_NONBLOCK)
        channel.add_watch(gobject.IO_IN, self._on_listener)
        channel.add_watch(gobject.IO_HUP | gobject.IO_ERR, self._on_not_listener)
        self.t_s = s
        self.t_c = channel

    def _on_listener(self, channel, pspec):
        print "Punching listener connected"
        sock = self.t_s.accept()[0]
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        print sock.getsockname()
        print sock.getpeername()

    def _on_not_listener(self, channel, condition):
        print condition
        print "Punching listener failed"

    def _on_echo_server_answered(self, local_ip, local_port, extern_ip,
            extern_port):
        self._transport_manager._update_transport_addresses(self,
                local_ip, local_port, extern_ip, extern_port)
        self.start_timeout("test", 1, local_ip, local_port, extern_ip,
            extern_port)

    def on_test_timeout(self, local_ip, local_port, extern_ip, extern_port):
        logger.info("Bind to port %i" % (local_port))
        self._transport.bind("", local_port)
        logger.info("Listen on %s:%i" % (local_ip, local_port))
        self._listen(local_ip, local_port)
        logger.info("Connect to %s(%i)" % (self._ip, self._port))
        self._transport._open(self._ip, self._port)

    def _on_echo_server_failed(self):
        logger.info("Connect to %s(%i)" % (self._ip, self._port))
        self._transport.open()

    def _on_echo_transport_status_changed(self, transport, param):
        status = transport.get_property("status")
        if status == IoStatus.OPEN:
            local_addr = transport.sockname
            logger.info("Sending echo server request (%s:%i)" % local_addr)
            tr_id = 12
            self._echo_requests[tr_id] = local_addr
            request = "\x02\x01\x41\x31\x41\x31\x41\x31\x00\x00\x00\x00\x00\x00\x00\x00\x5d\x00\x00\x00"
            transport.send(request)

    def _on_echo_transport_error(self, transport, error):
        pass #FIXME

    def _on_echo_transport_received(self, transport, data, length):
        if length != 20:
            print "length != 20"
            return
        fields = struct.unpack("!BBHIHHII", data)
        ver, code, port, ip, discard_port, test_port, test_ip, tr_id = fields
        port ^= 0x4131
        ip = socket.inet_ntoa(struct.pack("!I", ip ^ 0x41314131))
        logger.info("Received echo server answer (%s:%i)" % (ip, port))
        local_ip, local_port = self._echo_requests[12]
        handles, callback, errback = self._echo_transports[transport]
        for handle in handles:
            transport.disconnect(handle)
        del self._echo_requests[12]
        del self._echo_transports[transport]
        transport.close()
        gobject.idle_add(self._dispose_faulty_transport, transport)
        callback[0](local_ip, local_port, ip, port, *callback[1:])

class NATDetectionService(NATTraversalService):

    def __init__(self):
        NATTraversalService.__init__(self)

    def detect_nat_type(self):
        #http://miranda.googlecode.com/svn/trunk/miranda/protocols/MSN/msn_natdetect.cpp
        pass
