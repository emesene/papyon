# -*- coding: utf-8 -*-
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
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
#

from HTTPConnect import *
from SOCKS4 import *
from SOCKS5 import *

def ProxyFactory(client, proxies):
    if 'socks' in proxies:
        # FIXME we assume "socks://" is a SOCKS5 proxy
        proxy = SOCKS5Proxy(client, proxies['socks'])
    elif 'socks5' in proxies:
        proxy = SOCKS5Proxy(client, proxies['socks5'])
    elif 'socks4' in proxies:
        proxy = SOCKS4Proxy(client, proxies['socks4'])
    else:
        proxy = client
    return proxy
