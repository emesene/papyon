# -*- coding: utf-8 -*-
#
# Copyright (C) 2005  Ole André Vadla Ravnås <oleavr@gmail.com>
# Copyright (C) 2006-2007  Ali Sabil <ali.sabil@gmail.com>
# Copyright (C) 2007  Johann Prieur <johann.prieur@gmail.com>
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
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#
from papyon.gnet.constants import *

import gobject

__all__ = ['AbstractClient']

class AbstractClient(gobject.GObject):
    """Abstract client base class.
    All network client classes implements this interface.

        @sort: __init__, open, send, close
        @undocumented: do_*, _configure, _pre_open, _post_open

        @since: 0.1"""

    __gproperties__ = {
            "status": (gobject.TYPE_INT,
                "Connection Status",
                "The status of this connection.",
                0, 3, IoStatus.CLOSED,
                gobject.PARAM_READABLE)
            }

    __gsignals__ = {
            "error": (gobject.SIGNAL_RUN_FIRST,
                gobject.TYPE_NONE,
                (object,)),

            "received": (gobject.SIGNAL_RUN_FIRST,
                gobject.TYPE_NONE,
                (object, gobject.TYPE_ULONG)),

            "sent": (gobject.SIGNAL_RUN_FIRST,
                gobject.TYPE_NONE,
                (object, gobject.TYPE_ULONG)),
            }

    def __init__(self, host, port, domain=AF_INET, type=SOCK_STREAM):
        """Initializer

            @param host: the hostname to connect to.
            @type host: string

            @param port: a port number to connect to
            @type port: integer > 0 and < 65536

            @param domain: the communication domain.
            @type domain: integer
            @see socket module

            @param type: the communication semantics
            @type type: integer
            @see socket module
        """
        gobject.GObject.__init__(self)
        self._host = host
        self._port = port
        self._domain = domain
        self._type = type
        self._transport = None
        self.__status = IoStatus.CLOSED

    def __del__(self):
        self.close()

    # opening state methods
    def _configure(self):
        if len(self._host) == 0 or self._port < 0 or self._port > 65535:
            raise ValueError("Wrong host or port number : (%s, %d)" % \
                    (self._host, self._port) )
        if self.status in (IoStatus.OPENING, IoStatus.OPEN):
            return False
        assert(self.status == IoStatus.CLOSED)
        return True

    def _pre_open(self, io_object=None):
        self._status = IoStatus.OPENING

    def _post_open(self):
        pass

    # public API
    def open(self):
        """Open the connection."""
        raise NotImplementedError


    def close(self):
        """Close the connection."""
        raise NotImplementedError

    def send(self, buffer, callback=None, errback=None):
        """Send data to the server.

            @param buffer: data buffer.
            @type buffer: string

            @param callback: a callback method that would be called when the
                data is actually sent to the server.
            @type callback: tuple(callable, args)

            @param errback: a callback method called if sending fails.
            @type errback: tuple(callable, args)
        """
        raise NotImplementedError

    # properties
    def __get_host(self):
        "The remote host to connect to."
        return self._host
    def __set_host(self, host):
        if len(host) == 0:
            raise ValueError("Wrong host %s" % self._host)
        self._host = host
    host = property(__get_host, __set_host)

    def __get_port(self):
        "The remote port to connect to."
        return self._port
    def __set_port(self, port):
        if port < 0 or port > 65535:
            raise ValueError("Wrong port %d" % port)
        self._port = port
    port = property(__get_port, __set_port)

    def __get_sockname(self):
        return self._transport.getsockname()
    sockname = property(__get_sockname, None)

    @property
    def domain(self):
        return self._domain

    @property
    def type(self):
        return self._type

    @property
    def protocol(self):
        raise NotImplementedError

    def __get_status(self):
        return self.__status
    def __set_status(self, new_status):
        if self.__status != new_status:
            self.__status = new_status
            self.notify("status")
    _status = property(__get_status, __set_status)
    status  = property(__get_status)

    def do_get_property(self, pspec):
        if pspec.name == "status":
            return self.__status
        else:
            raise AttributeError, "unknown property %s" % pspec.name

    def do_set_property(self, pspec, value):
         raise AttributeError, "unknown property %s" % pspec.name

gobject.type_register(AbstractClient)
