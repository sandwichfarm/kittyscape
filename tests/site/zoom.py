"""Send native keyboard input only to the harness-owned Xvfb display :103."""

import ctypes as ct
import ctypes.util
import json
import struct
import sys
import zlib
from pathlib import Path


class WindowAttributes(ct.Structure):
    _fields_ = [
        ("x", ct.c_int), ("y", ct.c_int), ("width", ct.c_int), ("height", ct.c_int),
        ("border_width", ct.c_int), ("depth", ct.c_int), ("visual", ct.c_void_p), ("root", ct.c_ulong),
        ("window_class", ct.c_int), ("bit_gravity", ct.c_int), ("win_gravity", ct.c_int),
        ("backing_store", ct.c_int), ("backing_planes", ct.c_ulong), ("backing_pixel", ct.c_ulong),
        ("save_under", ct.c_int), ("colormap", ct.c_ulong), ("map_installed", ct.c_int), ("map_state", ct.c_int),
        ("all_event_masks", ct.c_long), ("your_event_mask", ct.c_long), ("do_not_propagate_mask", ct.c_long),
        ("override_redirect", ct.c_int), ("screen", ct.c_void_p),
    ]


class XImage(ct.Structure):
    _fields_ = [("width", ct.c_int), ("height", ct.c_int), ("xoffset", ct.c_int), ("format", ct.c_int),
                ("data", ct.c_void_p), ("byte_order", ct.c_int), ("bitmap_unit", ct.c_int),
                ("bitmap_bit_order", ct.c_int), ("bitmap_pad", ct.c_int), ("depth", ct.c_int),
                ("bytes_per_line", ct.c_int), ("bits_per_pixel", ct.c_int),
                ("red_mask", ct.c_ulong), ("green_mask", ct.c_ulong), ("blue_mask", ct.c_ulong)]


def libraries():
    x11 = ct.CDLL(ctypes.util.find_library("X11"))
    xtest = ct.CDLL(ctypes.util.find_library("Xtst"))
    pointer, window = ct.c_void_p, ct.c_ulong
    prototypes = {
        "XOpenDisplay": ([ct.c_char_p], pointer),
        "XCloseDisplay": ([pointer], ct.c_int),
        "XDefaultRootWindow": ([pointer], window),
        "XQueryTree": ([pointer, window, ct.POINTER(window), ct.POINTER(window),
                        ct.POINTER(ct.POINTER(window)), ct.POINTER(ct.c_uint)], ct.c_int),
        "XGetWindowAttributes": ([pointer, window, ct.POINTER(WindowAttributes)], ct.c_int),
        "XFree": ([pointer], ct.c_int),
        "XSetInputFocus": ([pointer, window, ct.c_int, ct.c_ulong], ct.c_int),
        "XRaiseWindow": ([pointer, window], ct.c_int),
        "XMoveResizeWindow": ([pointer, window, ct.c_int, ct.c_int, ct.c_uint, ct.c_uint], ct.c_int),
        "XSync": ([pointer, ct.c_int], ct.c_int),
        "XStringToKeysym": ([ct.c_char_p], ct.c_ulong),
        "XKeysymToKeycode": ([pointer, ct.c_ulong], ct.c_uint),
        "XKeycodeToKeysym": ([pointer, ct.c_uint, ct.c_int], ct.c_ulong),
        "XGetImage": ([pointer, window, ct.c_int, ct.c_int, ct.c_uint, ct.c_uint, ct.c_ulong, ct.c_int], ct.POINTER(XImage)),
        "XDestroyImage": ([ct.POINTER(XImage)], ct.c_int),
    }
    for name, (arguments, result) in prototypes.items():
        getattr(x11, name).argtypes = arguments
        getattr(x11, name).restype = result
    xtest.XTestFakeKeyEvent.argtypes = [pointer, ct.c_uint, ct.c_int, ct.c_ulong]
    xtest.XTestFakeKeyEvent.restype = ct.c_int
    return x11, xtest


def verify_owner(owner):
    lock = Path("/tmp/.X103-lock")
    if lock.is_symlink() or not lock.is_file():
        raise RuntimeError("Display :103 has no ordinary owned lock file")
    if lock.read_text().strip() != str(owner):
        raise RuntimeError("Display :103 does not belong to the supplied Xvfb process")
    if Path(f"/proc/{owner}/comm").read_text().strip() != "Xvfb":
        raise RuntimeError("Display owner is not the expected Xvfb process")


def browser_window(x11, display):
    root, parent = ct.c_ulong(), ct.c_ulong()
    children, count = ct.POINTER(ct.c_ulong)(), ct.c_uint()
    x11.XQueryTree(display, x11.XDefaultRootWindow(display), ct.byref(root), ct.byref(parent), ct.byref(children), ct.byref(count))
    candidates = []
    try:
        for index in range(count.value):
            attributes = WindowAttributes()
            x11.XGetWindowAttributes(display, children[index], ct.byref(attributes))
            if attributes.map_state == 2 and attributes.width >= 200 and attributes.height >= 100:
                candidates.append((attributes.width * attributes.height, children[index]))
    finally:
        if children:
            x11.XFree(children)
    if not candidates:
        raise RuntimeError("No mapped browser window on owned display :103")
    return max(candidates)[1]


def press(x11, xtest, display, names):
    codes = [x11.XKeysymToKeycode(display, x11.XStringToKeysym(name.encode())) for name in names]
    if not all(codes):
        raise RuntimeError("Requested key is absent from the isolated keyboard map")
    try:
        for code in codes:
            xtest.XTestFakeKeyEvent(display, code, True, 0)
    finally:
        for code in reversed(codes):
            xtest.XTestFakeKeyEvent(display, code, False, 0)
        x11.XSync(display, False)


def type_text(x11, xtest, display, text):
    shift = x11.XKeysymToKeycode(display, x11.XStringToKeysym(b"Shift_L"))
    for char in text:
        if not 32 <= ord(char) <= 126:
            raise ValueError("Native text input is restricted to printable ASCII")
        code = x11.XKeysymToKeycode(display, ord(char))
        shifted = x11.XKeycodeToKeysym(display, code, 0) != ord(char)
        if shifted:
            xtest.XTestFakeKeyEvent(display, shift, True, 0)
        xtest.XTestFakeKeyEvent(display, code, True, 0)
        xtest.XTestFakeKeyEvent(display, code, False, 0)
        if shifted:
            xtest.XTestFakeKeyEvent(display, shift, False, 0)
    x11.XSync(display, False)


def png_chunk(kind, body):
    return struct.pack("!I", len(body)) + kind + body + struct.pack("!I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def image_rows(image):
    pixel_bytes = image.bits_per_pixel // 8
    source = ct.string_at(image.data, image.bytes_per_line * image.height)
    offsets = [(mask.bit_length() - 1) // 8 for mask in (image.red_mask, image.green_mask, image.blue_mask)]
    if image.byte_order:
        offsets = [pixel_bytes - 1 - offset for offset in offsets]
    rows = bytearray()
    for y in range(image.height):
        row = source[y * image.bytes_per_line:y * image.bytes_per_line + image.width * pixel_bytes]
        rgb = bytearray(image.width * 3)
        for channel, offset in enumerate(offsets):
            rgb[channel::3] = row[offset::pixel_bytes]
        rows.extend(b"\0")
        rows.extend(rgb)
    return rows


def screenshot(x11, display, window, geometry, destination):
    path = Path(destination).resolve()
    if not str(path).startswith("/tmp/kittyscape-browser-zoom-"):
        raise ValueError("Native screenshots must stay in the dedicated temporary evidence directory")
    image = x11.XGetImage(display, window, 0, 0, geometry.width, geometry.height, ct.c_ulong(-1).value, 2)
    if not image:
        raise RuntimeError("Cannot capture the owned browser window")
    try:
        header = struct.pack("!IIBBBBB", geometry.width, geometry.height, 8, 2, 0, 0, 0)
        data = b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", header)
        data += png_chunk(b"IDAT", zlib.compress(image_rows(image.contents))) + png_chunk(b"IEND", b"")
        with path.open("xb") as stream:
            stream.write(data)
    finally:
        x11.XDestroyImage(image)


def main():
    owner, command = int(sys.argv[1]), json.loads(sys.argv[2])
    verify_owner(owner)
    x11, xtest = libraries()
    display = x11.XOpenDisplay(b":103")
    if not display:
        raise RuntimeError("Cannot connect to owned display :103")
    try:
        window = browser_window(x11, display)
        x11.XRaiseWindow(display, window)
        x11.XSetInputFocus(display, window, 2, 0)
        if command.get("prepare"):
            x11.XMoveResizeWindow(display, window, 0, 0, 1440, 1000)
        if "keys" in command:
            press(x11, xtest, display, command["keys"])
        if "text" in command:
            type_text(x11, xtest, display, command["text"])
        x11.XSync(display, False)
        geometry = WindowAttributes()
        x11.XGetWindowAttributes(display, window, ct.byref(geometry))
        if "screenshot" in command:
            screenshot(x11, display, window, geometry, command["screenshot"])
        print(json.dumps({"display": ":103", "owner": owner, "window": window,
                          "geometry": {"width": geometry.width, "height": geometry.height}}))
    finally:
        x11.XCloseDisplay(display)


if __name__ == "__main__":
    main()
