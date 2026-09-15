"""Resolve a test window's standard foreign-toplevel identifier for grim -T.

This read-only wire client uses ext-foreign-toplevel-list-v1, version 1. It never
exports another window's metadata. Only the exact, unique fixture title is returned.
"""

import os
import socket
import struct
from functools import partial


def _string(value):
    raw = value.encode() + b"\0"
    return struct.pack("<I", len(raw)) + raw + b"\0" * (-len(raw) % 4)


def _decode_string(payload, offset=0):
    length = struct.unpack_from("<I", payload, offset)[0]
    value = payload[offset + 4:offset + 4 + length - 1].decode("utf-8", "replace")
    return value, offset + 4 + (length + 3) // 4 * 4


def _send(connection, object_id, opcode, payload):
    connection.sendall(struct.pack("<II", object_id, ((len(payload) + 8) << 16) | opcode) + payload)


def _roundtrip(connection, callback_id, handler):
    _send(connection, 1, 0, struct.pack("<I", callback_id))
    buffer = b""
    completed = False
    while not completed:
        packet = connection.recv(65536)
        if not packet:
            raise RuntimeError("Wayland discovery connection closed")
        buffer += packet
        while len(buffer) >= 8:
            object_id, word = struct.unpack_from("<II", buffer)
            size, opcode = word >> 16, word & 65535
            if size < 8:
                raise RuntimeError("Invalid Wayland discovery message")
            if size > len(buffer):
                break
            handler(object_id, opcode, buffer[8:size])
            buffer = buffer[size:]
            if object_id == callback_id:
                completed = True


def _event(registry, handles, object_id, opcode, payload):
    if object_id == 2 and opcode == 0:
        name = struct.unpack_from("<I", payload)[0]
        interface, _ = _decode_string(payload, 4)
        registry[interface] = name
    elif object_id == 4 and opcode == 0:
        handles[struct.unpack_from("<I", payload)[0]] = {}
    elif object_id in handles and opcode in (2, 3, 4):
        handles[object_id][opcode] = _decode_string(payload)[0]


def identifier(title):
    registry, handles = {}, {}
    event = partial(_event, registry, handles)

    address = os.path.join(os.environ["XDG_RUNTIME_DIR"], os.environ["WAYLAND_DISPLAY"])
    with socket.socket(socket.AF_UNIX) as connection:
        connection.settimeout(3)
        connection.connect(address)
        _send(connection, 1, 1, struct.pack("<I", 2))
        _roundtrip(connection, 3, event)
        interface = "ext_foreign_toplevel_list_v1"
        if interface not in registry:
            raise RuntimeError("Compositor lacks foreign-toplevel capture discovery")
        payload = struct.pack("<I", registry[interface]) + _string(interface) + struct.pack("<II", 1, 4)
        _send(connection, 2, 0, payload)
        _roundtrip(connection, 5, event)
    matches = [handle[4] for handle in handles.values() if handle.get(2) == title and 4 in handle]
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one fixture toplevel handle")
    return matches[0]
