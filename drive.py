"""
Finds the media library on a USB drive, tolerating the two things that make
this annoying on a Pi at boot:

  1. The mount point isn't predictable (/media/<user>/<label> varies).
  2. The drive may not be mounted yet when the program starts (boot race).

The approach: scan the configured base directories (and one level down) for
any mounted directory that "looks like" a Jimflix library, retrying on a
timer until one appears. This makes both cold-boot races and later
hot-plugging just work.
"""

import os
import time

import config


def _looks_like_library(path):
    """
    A library root is a directory matching the expected shape

        <root>/<MediaType>/<Title>/<a video file>

    i.e. there exists at least one video file exactly two directory levels
    down. Requiring the video file (rather than just nested folders) is what
    distinguishes a real library root from a mount *container* like /media or
    /media/<user>, which would otherwise look library-shaped one level too
    high and turn usernames into "categories".
    """
    try:
        if not os.path.isdir(path):
            return False
        for type_name in os.listdir(path):
            type_path = os.path.join(path, type_name)
            if not os.path.isdir(type_path):
                continue
            try:
                title_names = os.listdir(type_path)
            except (PermissionError, OSError):
                continue
            for title_name in title_names:
                title_path = os.path.join(type_path, title_name)
                if not os.path.isdir(title_path):
                    continue
                try:
                    for fname in os.listdir(title_path):
                        if (os.path.isfile(os.path.join(title_path, fname))
                                and fname.lower().endswith(config.VIDEO_EXTENSIONS)):
                            return True
                except (PermissionError, OSError):
                    continue
    except (PermissionError, OSError):
        return False
    return False


def _candidate_roots(bases):
    """Yield plausible library-root paths: each base, and each child of each base."""
    for base in bases:
        if not os.path.isdir(base):
            continue
        # The base itself (e.g. someone mounts straight to /mnt/usb).
        yield base
        # One level down (e.g. /media/<user>, then /media/<user>/<label>).
        try:
            for child in sorted(os.listdir(base)):
                child_path = os.path.join(base, child)
                if os.path.isdir(child_path):
                    yield child_path
                    # Two levels: /media/<user>/<label>
                    try:
                        for grandchild in sorted(os.listdir(child_path)):
                            gc_path = os.path.join(child_path, grandchild)
                            if os.path.isdir(gc_path):
                                yield gc_path
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            continue


def find_library_root():
    """
    Return the path to a library root right now, or None if none is found.
    Honors config.LIBRARY_PATH_OVERRIDE if set.
    """
    if config.LIBRARY_PATH_OVERRIDE:
        path = config.LIBRARY_PATH_OVERRIDE
        return path if os.path.isdir(path) else None

    for candidate in _candidate_roots(config.DRIVE_SCAN_BASES):
        if _looks_like_library(candidate):
            return candidate
    return None


def wait_for_library_root(timeout_s, poll_interval_s, on_tick=None):
    """
    Poll for a library root until found or timeout elapses.

    on_tick(elapsed_seconds) is called once per poll cycle -- the UI uses it
    to keep the splash screen painted and the window responsive while waiting.

    Returns the path, or None if the timeout elapses (the caller can keep
    retrying later to support hot-plug).
    """
    start = time.monotonic()
    while True:
        root = find_library_root()
        if root:
            return root
        elapsed = time.monotonic() - start
        if on_tick:
            on_tick(elapsed)
        if elapsed >= timeout_s:
            return None
        time.sleep(poll_interval_s)
