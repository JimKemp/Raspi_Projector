"""
Display/audio backend setup for running on a Pi WITHOUT a desktop (console
boot, no X11). Import and call configure_backends() BEFORE pygame.init() and
before creating the UI.

On a console-only Pi, pygame must render straight to the screen via KMS/DRM
instead of through an X server. SDL picks its video driver from the
SDL_VIDEODRIVER environment variable; we set it to "kmsdrm" (the modern,
robust path on current Raspberry Pi OS), unless a DISPLAY is present (meaning
we're actually inside a desktop session, e.g. during laptop/desktop testing),
in which case we leave SDL to auto-detect X11.

Audio: pygame's mixer init can fail or spew ALSA warnings on a headless box.
We make the mixer optional so a sound-system hiccup can never stop the UI
from coming up -- VLC handles movie audio itself anyway, independent of
pygame's mixer.
"""

import os


def configure_backends():
    """Set SDL environment variables appropriately. Call before pygame.init()."""
    # If a real X display is present, we're inside a desktop session -- don't
    # force kmsdrm, let SDL use X11. This keeps laptop/desktop testing working.
    if os.environ.get("DISPLAY"):
        return "x11 (DISPLAY present)"

    # Console/headless: render via KMS/DRM. Only set it if the user hasn't
    # already chosen a driver, so manual overrides still win.
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")

    # Some console setups need a hint about which framebuffer/card to use;
    # leaving it unset lets SDL auto-pick, which is correct on most Pis.
    # Silence the mouse cursor requirement on dummy/kms contexts.
    os.environ.setdefault("SDL_VIDEO_KMSDRM_LEGACY_DRM_DRIVER", "0")
    return f"console ({os.environ.get('SDL_VIDEODRIVER')})"


def init_pygame_safely():
    """
    Initialize pygame with audio failures made non-fatal.

    Returns (pygame_module, audio_ok). The UI works regardless of audio_ok;
    only pygame's own sound effects would be unavailable (which Jimflix
    doesn't use -- VLC plays movie audio on its own).
    """
    import pygame

    # Initialize the display/video and other subsystems, but NOT the mixer yet.
    pygame.display.init()
    pygame.font.init()

    audio_ok = False
    try:
        pygame.mixer.init()
        audio_ok = True
    except Exception:
        # Headless ALSA/Pulse problems land here; ignore and continue.
        audio_ok = False

    return pygame, audio_ok
