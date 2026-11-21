"""Garde-fou réseau pour les tests : toute connexion hors de la machine locale échoue.

Deux couches (voir test_no_outbound.py) :
1. dynamique : ce module remplace connect/getaddrinfo pour refuser tout hôte non local ;
2. statique : une analyse du code refuse les bibliothèques ou URL externes.
"""

import ipaddress
import socket


class OutboundConnectionBlocked(AssertionError):
    """Du code a tenté une connexion sortante : violation de la contrainte C1."""


def _is_local_host(host) -> bool:
    if host in (None, "", "localhost", "ip6-localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _check_address(address) -> None:
    if isinstance(address, tuple):          # (hôte, port, ...) ; les sockets Unix sont des str
        host = address[0]
        if isinstance(host, bytes):
            host = host.decode()
        if not _is_local_host(host):
            raise OutboundConnectionBlocked(f"connexion sortante interdite vers {host!r}")


def install():
    originals = (socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo)
    real_connect, real_connect_ex, real_getaddrinfo = originals

    def connect(self, address):
        _check_address(address)
        return real_connect(self, address)

    def connect_ex(self, address):
        _check_address(address)
        return real_connect_ex(self, address)

    def getaddrinfo(host, *args, **kwargs):
        if not _is_local_host(host):
            raise OutboundConnectionBlocked(f"résolution DNS interdite pour {host!r}")
        return real_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = connect
    socket.socket.connect_ex = connect_ex
    socket.getaddrinfo = getaddrinfo

    def uninstall():
        socket.socket.connect, socket.socket.connect_ex, socket.getaddrinfo = originals

    return uninstall
