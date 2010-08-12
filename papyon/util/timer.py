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

import gobject

__all__ = ['Timer']

class Timer(object):

    def __init__(self):
        self._timeout_sources = {} # name => source
        self._timeout_args = {} # name => callback args

    @property
    def timeouts(self):
        return self._timeout_sources.keys()

    def start_timeout(self, name, time, *cb_args):
        self.stop_timeout(name)
        source = gobject.timeout_add_seconds(time, self.on_timeout, name)
        self._timeout_sources[name] = source
        self._timeout_args[name] = cb_args

    def stop_timeout(self, name):
        source = self._timeout_sources.get(name, None)
        if source is not None:
            gobject.source_remove(source)
            del self._timeout_sources[name]
        if name in self._timeout_args:
            return self._timeout_args.pop(name)
        return []

    def stop_all_timeout(self):
        for (name, source) in self._timeout_sources.items():
            if source is not None:
                gobject.source_remove(source)
        self._timeout_sources.clear()
        self._timeout_args.clear()

    def on_timeout(self, name):
        cb_args = self.stop_timeout(name)
        handler = getattr(self, "on_%s_timeout" % name, None)
        if handler is not None:
            handler(*cb_args)
