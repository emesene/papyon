# -*- coding: utf-8 -*-
#
# papyon - a python client library for Msn
#
# Copyright (C) 2007 Ali Sabil <ali.sabil@gmail.com>
# Copyright (C) 2008 Richard Spiers<richard.spiers@gmail.com>
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

from papyon.gnet.message.HTTP import HTTPMessage
from papyon.msnp2p.constants import SLPContentType, SLPStatus
from papyon.msnp2p.errors import SLPParseError
from papyon.util.encoding import b64_decode

import base64
import uuid

__all__ = ['SLPMessage', 'SLPRequestMessage', 'SLPResponseMessage',
           'SLPMessageBody', 'SLPNullBody', 'SLPSessionRequestBody',
           'SLPSessionCloseBody', 'SLPSessionFailureResponseBody',
           'SLPTransportRequestBody', 'SLPTransportResponseBody']


class SLPMessage(HTTPMessage):
    STD_HEADERS = ["To", "From", "Via", "CSeq", "Call-ID", "Max-Forwards"]

    def __init__(self, to="", frm="", branch="", cseq=0, call_id="",
            max_forwards=0, on_behalf=""):
        HTTPMessage.__init__(self)
        self.add_header("To", "<msnmsgr:%s>" % to)
        self.add_header("From", "<msnmsgr:%s>" % frm)
        if branch:
            self.add_header("Via", "MSNSLP/1.0/TLP ;branch=%s" % branch)
        self.add_header("CSeq", str(cseq))
        if call_id:
            self.add_header("Call-ID", call_id)
        self.add_header("Max-Forwards", str(max_forwards))
        if on_behalf:
            self.add_header("On-Behalf", on_behalf)

        # Make the body a SLP Message wih "null" content type
        self.body = SLPNullBody()

    @property
    def to(self):
        to = self.get_header("To")
        return to.split(":", 1)[1][:-1]

    @property
    def frm(self):
        frm = self.get_header("From")
        return frm.split(":", 1)[1][:-1]

    @property
    def branch(self):
        try:
            via = self.get_header("Via")
            params = via.split(";", 1)[1:]

            for param in params:
                key, value = param.split('=')
                if key.strip() == "branch":
                    return value.strip()
            return ""
        except KeyError:
            return ""

    @property
    def cseq(self):
        return int(self.get_header("CSeq"))

    @property
    def call_id(self):
        try:
            return self.get_header("Call-ID")
        except KeyError:
            return ""

    def parse(self, chunk):
        HTTPMessage.parse(self, chunk)

        content_type = self.headers.get("Content-Type", "null")
        
        raw_body = self.body
        self.body = SLPMessageBody.build(content_type, raw_body)
        
    def __str__(self):
        if self.body is None:
            self.add_header("Content-Type", "null")
            self.add_header("Content-Length", 0)
        else:
            self.add_header("Content-Type", self.body.type)
            self.add_header("Content-Length", len(str(self.body)))
            
        return HTTPMessage.__str__(self)

    @staticmethod
    def build(raw_message):
        if raw_message.find("MSNSLP/1.0") < 0 or raw_message.find("\r\n") < 0:
            raise SLPParseError("message doesn't seem to be an MSNSLP/1.0 message")

        # parse start line to determine if it's a response or a request
        try:
            start_line, content = raw_message.split("\r\n", 1)
            start_line = start_line.split(" ")

            if start_line[0].strip() == "MSNSLP/1.0":
                status = int(start_line[1].strip())
                reason = " ".join(start_line[2:]).strip()
                slp_message = SLPResponseMessage(status, reason)
            else:
                method = start_line[0].strip()
                resource = start_line[1].strip()
                slp_message = SLPRequestMessage(method, resource)
        except:
            raise SLPParseError("invalid start line: %s" % start_line)

        # parse message content
        slp_message.parse(content)

        # make sure mandatory headers are present and valid
        for attr, name in (('to', 'To'), ('frm', 'From'), ('cseq', 'CSeq')):
            try:
                value = getattr(slp_message, attr)
            except:
                raise SLPParseError("invalid or missing %s header" % name)
        
        return slp_message


class SLPRequestMessage(SLPMessage):
    def __init__(self, method, resource, *args, **kwargs):
        SLPMessage.__init__(self, *args, **kwargs)
        self.method = method
        self.resource = resource
        
        self._to = resource.split(":", 1)[1]

    def __get_to(self):
        return self._to
    def __set_to(self, to):
        self._to = to
        self.resource = "MSNMSGR:" + to
        self.add_header("To", "<msnmsgr:%s>" % to)
    to = property(__get_to, __set_to)

    def __str__(self):
        message = SLPMessage.__str__(self)
        start_line = "%s %s MSNSLP/1.0" % (self.method, self.resource)
        return start_line + "\r\n" + message


class SLPResponseMessage(SLPMessage):
    STATUS_MESSAGE =  {
            200 : "OK",
            404 : "Not Found",
            500 : "Internal Error",
            603 : "Decline",
            606 : "Unacceptable"}

    def __init__(self, status, reason=None, *args, **kwargs):
        SLPMessage.__init__(self, *args, **kwargs)
        self.status = int(status)
        self.reason = reason
    
    def __str__(self):
        message = SLPMessage.__str__(self)
        
        if self.reason is None:
            reason = SLPResponseMessage.STATUS_MESSAGE[self.status]
        else:
            reason = self.reason
            
        start_line = "MSNSLP/1.0 %d %s" % (self.status, reason)
        return start_line + "\r\n" + message


class SLPMessageBody(HTTPMessage):
    content_classes = {}

    def __init__(self, content_type, session_id=None, s_channel_state=0, capabilities_flags=1):
        HTTPMessage.__init__(self)
        self.type = content_type

        if session_id is not None:
            self.add_header("SessionID", session_id)
        if s_channel_state is not None:
            self.add_header("SChannelState", s_channel_state)
        if capabilities_flags is not None:
            self.add_header("Capabilities-Flags", capabilities_flags)

    @property
    def session_id(self):
        try:
            return int(self.get_header("SessionID"))
        except (KeyError, ValueError):
            return 0
        
    @property
    def s_channel_state(self):
        try:
            return int(self.get_header("SChannelState"))
        except (KeyError, ValueError):
            return 0
        
    @property
    def capabilities_flags(self):
        try:
            return int(self.get_header("Capabilities-Flags"))
        except (KeyError, ValueError):
            return 0
  
    def parse(self, data):
        if len(data) == 0:
            return
        data = data.rstrip('\x00')
        HTTPMessage.parse(self, data)

    def __str__(self):
        return HTTPMessage.__str__(self) + "\x00"
    
    @staticmethod
    def register_content(content_type, cls):
        SLPMessageBody.content_classes[content_type] = cls

    @staticmethod
    def build(content_type, content):
        if content_type in SLPMessageBody.content_classes.keys():
            cls = SLPMessageBody.content_classes[content_type]
            body = cls();
        else:
            body = SLPMessageBody(content_type)

        body.parse(content)
        return body


class SLPNullBody(SLPMessageBody):
    def __init__(self):
        SLPMessageBody.__init__(self, SLPContentType.NULL)
SLPMessageBody.register_content(SLPContentType.NULL, SLPNullBody)


class SLPSessionRequestBody(SLPMessageBody):
    def __init__(self, euf_guid=None, app_id=None, context=None,
            session_id=None, s_channel_state=0, capabilities_flags=1):
        SLPMessageBody.__init__(self,SLPContentType.SESSION_REQUEST,
                                    session_id, s_channel_state, capabilities_flags)

        if euf_guid is not None:
            self.add_header("EUF-GUID", euf_guid)
        if app_id is not None:
            self.add_header("AppID", app_id)
        if context is not None:
            self.add_header("Context",  base64.b64encode(context))

    @property
    def euf_guid(self):
        try:
            return self.get_header("EUF-GUID")
        except (KeyError, ValueError):
            return ""

    @property
    def context(self):
        try:
            context = self.get_header("Context")
            return b64_decode(context)
        except (KeyError, TypeError):
            return None

    @property
    def application_id(self):
        try:
            return int(self.get_header("AppID"))
        except (KeyError, ValueError):
            return 0

SLPMessageBody.register_content(SLPContentType.SESSION_REQUEST, SLPSessionRequestBody)

class SLPTransportRequestBody(SLPMessageBody):
    def __init__(self, session_id=None, s_channel_state=None,
            capabilities_flags=None, bridges=[], conn_type="Unknown-Connect",
            upnp=False, firewall=False):
        SLPMessageBody.__init__(self,SLPContentType.TRANSPORT_REQUEST,
                                    session_id, s_channel_state, capabilities_flags)

        self.add_header("NetID",-1388627126)
        self.add_header("Bridges", " ".join(bridges))
        self.add_header("Conn-Type", conn_type)
        self.add_header("TCP-Conn-Type", conn_type)
        self.add_header("UPnPNat", upnp and "true" or "false")
        self.add_header("ICF", firewall and "true" or "false")
        self.add_header("Nonce", "{%s}" % str(uuid.uuid4()).upper())
        self.add_header("Nat-Trav-Msg-Type", "WLX-Nat-Trav-Msg-Direct-Connect-Req")

    @property
    def bridges(self):
        try:
            return self.get_header("Bridges").split(" ")
        except (KeyError, ValueError):
            return []

    @property
    def nonce(self):
        try:
            return uuid.UUID(self.get_header("Nonce")[1:-1])
        except (KeyError, ValueError):
            return ""

SLPMessageBody.register_content(SLPContentType.TRANSPORT_REQUEST, SLPTransportRequestBody)

class SLPTransportResponseBody(SLPMessageBody):
    def __init__(self, bridge=None, listening=None, nonce=None, internal_ips=None,
            internal_port=None, external_ips=None, external_port=None,
            session_id=None, s_channel_state=None, capabilities_flags=None,
            conn_type="Unknown-Connect", version=1):
        SLPMessageBody.__init__(self,SLPContentType.TRANSPORT_RESPONSE,
                                    session_id, s_channel_state, capabilities_flags)

        self._version = version

        if bridge is not None:
            self.add_header("Bridge", bridge)
        if listening is not None:
            self.add_header("Listening", listening and "true" or "false")
        if nonce is not None:
            self.add_header("Nonce", "{%s}" % str(nonce).upper())
        if internal_ips is not None:
            internal_ips = " ".join(internal_ips)
            self._add_header("IPv4Internal-Addrs", internal_ips)
        if internal_port is not None:
            self._add_header("IPv4Internal-Port", str(internal_port))
        if external_ips is not None:
            external_ips = " ".join(external_ips)
            self._add_header("IPv4External-Addrs", external_ips)
        if external_port is not None:
            self._add_header("IPv4External-Port", str(external_port))
        self.add_header("Nat-Trav-Msg-Type", "WLX-Nat-Trav-Msg-Direct-Connect-Req")
        self.add_header("Conn-Type", conn_type)
        self.add_header("TCP-Conn-Type", conn_type)
        self.add_header("IPv6-global", "")

    def _add_header(self, name, value):
        ''' add_header convenience method for p2pv1 and p2pv2'''
        if self._version >= 2:
            self.add_header(name[::-1], value[::-1])
        else:
            self.add_header(name, value)

    def _get_header(self, name):
        ''' get_header convenience method for p2pv1 and p2pv2'''
        if self._version >= 2:
            return self.get_header(name[::-1])[::-1]
        else:
            return self.get_header(name)

    @property
    def bridge(self):
        try:
            return self.get_header("Bridge")
        except (KeyError, ValueError):
            return ""

    @property
    def listening(self):
        try:
            listening = self.get_header("Listening").lower()
            return (listening == "true")
        except KeyError:
            return False

    @property
    def nonce(self):
        try:
            return uuid.UUID(self.get_header("Nonce")[1:-1])
        except (KeyError, ValueError):
            return ""

    @property
    def internal_ips(self):
        try:
            return self._get_header("IPv4Internal-Addrs").split()
        except (KeyError, ValueError):
            return []

    @property
    def internal_port(self):
        try:
            return int(self._get_header("IPv4Internal-Port"))
        except (KeyError, ValueError):
            return 0

    @property
    def external_ips(self):
        try:
            return self._get_header("IPv4External-Addrs").split()
        except (KeyError, ValueError):
            return []

    @property
    def external_port(self):
        try:
            return int(self._get_header("IPv4External-Port"))
        except (KeyError, ValueError):
            return 0

SLPMessageBody.register_content(SLPContentType.TRANSPORT_RESPONSE, SLPTransportResponseBody)

class SLPSessionCloseBody(SLPMessageBody):
    def __init__(self, context=None, session_id=None, reason=None,
            s_channel_state=None, capabilities_flags=None):
        SLPMessageBody.__init__(self, SLPContentType.SESSION_CLOSE,
                session_id, s_channel_state, capabilities_flags)

        if context is not None:
            self.add_header("Context", base64.b64encode(context));
        if reason is not None:
            if reason[0] == SLPStatus.ACCEPTED:
                self.add_header("AcceptedBy", "{%s}" % str(reason[1]).upper())
            elif reason[0] == SLPStatus.DECLINED:
                self.add_header("DeclinedBy", "{%s}" % str(reason[1]).upper())

    @property
    def context(self):
        try:
            context = self.get_header("Context")
            return b64_decode(context)
        except (KeyError, TypeError):
            return None

SLPMessageBody.register_content(SLPContentType.SESSION_CLOSE, SLPSessionCloseBody)


class SLPSessionFailureResponseBody(SLPMessageBody):
    def __init__(self, session_id=None, s_channel_state=0, capabilities_flags=1):
        SLPMessageBody.__init__(self, SLPContentType.SESSION_FAILURE,
                session_id, s_channel_state, capabilities_flags)

SLPMessageBody.register_content(SLPContentType.SESSION_FAILURE, SLPSessionFailureResponseBody)
