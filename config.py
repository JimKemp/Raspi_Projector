"""
Jimflix configuration -- every knob you're likely to touch lives here.
The other modules read from this file and shouldn't need editing for normal
customization (colors, pins, paths, remote mapping, etc.).
"""

# ---------------------------------------------------------------------------
# Library / drive detection
# ---------------------------------------------------------------------------
# Expected layout on the USB drive:
#     <root>/<MediaType>/<Title>/<video file>
#                                /<info.yaml>      (optional)
#                                /description.txt  (optional)
#                                /cover.jpg        (optional)
# e.g.  Movies/Frau im Mond/frau_im_mond.mkv
#
# Set LIBRARY_PATH_OVERRIDE to a fixed path to skip auto-detection entirely
# (useful for testing on a laptop -- point it at a folder of test media).
LIBRARY_PATH_OVERRIDE = None

# Where to look for mounted removable drives. Auto-detection scans these
# bases (and one level of subdirectories, e.g. /media/<user>/<label>).
DRIVE_SCAN_BASES = ["/media", "/mnt", "/run/media"]

# Startup waits this long for a drive before showing an "insert drive"
# screen. It KEEPS scanning after that, so hot-plugging still works.
DRIVE_WAIT_TIMEOUT_S = 30
DRIVE_POLL_INTERVAL_S = 1.0

VIDEO_EXTENSIONS = (".mp4", ".mkv", ".avi", ".mov", ".m4v", ".webm", ".mpg", ".mpeg")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")

# Preferred cover filenames (any image extension). If none match, the first
# image file found in the title folder is used.
COVER_BASENAMES = ("cover", "poster", "folder", "thumb")
# Preferred metadata filenames. Any *.yaml / *.yml in the folder is accepted
# as a fallback.
YAML_BASENAMES = ("info", "meta", "movie", "metadata")
DESCRIPTION_FILENAME = "description.txt"

# ---------------------------------------------------------------------------
# Splash screen
# ---------------------------------------------------------------------------
SPLASH_TEXT = "Jimflix"
SPLASH_MIN_SECONDS = 1.0          # stay on splash at least this long, even if load is instant

# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
SCREEN_SIZE = (1280, 720)          # projector native 720p
FULLSCREEN = True
TARGET_FPS = 30

# ---------------------------------------------------------------------------
# Colors (R, G, B)
# ---------------------------------------------------------------------------
BG_COLOR = (16, 16, 20)
PANEL_COLOR = (30, 30, 38)
TEXT_COLOR = (236, 236, 236)
DIM_TEXT_COLOR = (150, 150, 162)
HIGHLIGHT_COLOR = (255, 140, 0)
SPLASH_BG_COLOR = (12, 12, 16)
PLACEHOLDER_COLOR = (52, 52, 64)

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------
FONT_NAME = None                   # None = pygame default; or a path to a .ttf
FONT_SIZE_SPLASH = 96
FONT_SIZE_HEADER = 46
FONT_SIZE_ITEM = 30
FONT_SIZE_BODY = 26
FONT_SIZE_SMALL = 22

# ---------------------------------------------------------------------------
# Grid layout (cover browser)
# ---------------------------------------------------------------------------
GRID_COLUMNS = 5
COVER_W = 184
COVER_H = 264
GRID_H_SPACING = 28
GRID_V_SPACING = 56
GRID_TOP = 96
GRID_LEFT = 56

# ---------------------------------------------------------------------------
# IR remote
# ---------------------------------------------------------------------------
# Maps decoded NEC codes -> semantic actions used by the UI.
# Codes captured with ir_logger.py from your RCA remote.
#
# NOTE: your notes listed two buttons as "Volume minus". Based on the
# remote's [-] [mute] [+] layout, the second one is assumed to be Volume
# PLUS. If volume up/down feel reversed, swap these two lines.
IR_KEYMAP = {
    0x1068E11E: "power",       # Power
    0x10683BC4: "m",           # M
    0x106851AE: "home",        # Home
    0x106821DE: "up",          # Keypad up
    0x1068B14E: "down",        # Keypad down
    0x1068DD22: "left",        # Keypad left
    0x1068718E: "right",       # Keypad right
    0x10684DB2: "ok",          # Keypad OK
    0x10682DD2: "vol_down",    # Volume minus
    0x1068619E: "vol_up",      # Volume plus  (your notes said "minus" -- assumed plus)
    0x1068D12E: "mute",        # Volume mute
    0x1068AD52: "menu",        # Menu
    0x1068916E: "back",        # Back
    0x106813EC: "play_pause",  # Play/pause
}

IR_GPIO_PIN = 18                   # BCM pin the VS838 OUT line is wired to
IR_REPEAT_SUPPRESS_S = 0.18        # ignore repeat frames of the same code within this window

# What the Power button does. Options: "ignore", "quit" (exit Jimflix to a
# console), "shutdown" (power off the Pi). Defaulting to "ignore" so a stray
# press can't kill the box mid-movie.
POWER_BUTTON_ACTION = "ignore"

# ---------------------------------------------------------------------------
# VLC playback (controlled over its rc socket interface)
# ---------------------------------------------------------------------------
VLC_RC_HOST = "localhost"
VLC_RC_PORT = 4212
VLC_VOLUME_START = 256             # rc volume units (~256 = 100%)
VLC_VOLUME_STEP = 32
VLC_VOLUME_MAX = 512
