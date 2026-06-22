#!/usr/bin/env python3
"""
Jimflix -- a minimal IR-remote-driven media browser/player for a Pi + projector.

Flow:
    SPLASH ──(drive found, scanned, >=1s elapsed)──► CATEGORIES
       │                                                  │ OK
       │ (no drive after timeout) ──► keeps retrying      ▼
                                                       GRID ──OK──► DETAIL ──Play──► PLAYING
                                                         ▲ Back       │ Back          │ Back
                                                         └────────────┘◄──────────────┘

Input comes from the IR remote (ir_input). Arrow keys / Enter / etc. mirror
the remote so the whole thing can be exercised on a laptop with no GPIO.
Customize everything in config.py.
"""

import sys
import time

# Configure SDL's video/audio backend BEFORE pygame is initialized. On a
# console-only Pi this selects KMS/DRM rendering; inside a desktop session it
# leaves X11 auto-detection alone. Must happen before `import pygame` does any
# initialization, so it's first.
import display_backend
_BACKEND = display_backend.configure_backends()

import pygame

import config
import drive
import library
from ir_input import IRRemote
from player import Player
from ui import UI

# UI states
SPLASH = "splash"
NO_DRIVE = "no_drive"
EMPTY = "empty"
CATEGORIES = "categories"
GRID = "grid"
DETAIL = "detail"
PLAYING = "playing"


# Keyboard -> action map, mirroring the IR remote for laptop testing.
KEY_ACTIONS = {
    pygame.K_UP: "up",
    pygame.K_DOWN: "down",
    pygame.K_LEFT: "left",
    pygame.K_RIGHT: "right",
    pygame.K_RETURN: "ok",
    pygame.K_BACKSPACE: "back",
    pygame.K_SPACE: "play_pause",
    pygame.K_h: "home",
    pygame.K_m: "menu",
    pygame.K_EQUALS: "vol_up",
    pygame.K_MINUS: "vol_down",
    pygame.K_0: "mute",
}


class Jimflix:
    def __init__(self):
        # Audio-tolerant init: a headless ALSA/Pulse failure won't stop the UI.
        display_backend.init_pygame_safely()
        print(f"Jimflix display backend: {_BACKEND}", flush=True)
        self.ui = UI()
        self.remote = IRRemote(
            config.IR_GPIO_PIN, config.IR_KEYMAP, config.IR_REPEAT_SUPPRESS_S
        )
        self.player = Player()
        self.clock = pygame.time.Clock()

        self.state = SPLASH
        self.categories = []
        self.root = None
        self.running = True
        self.dirty = True

        # selection cursors
        self.cat_idx = 0
        self.grid_idx = 0
        self.grid_scroll = 0
        self.episode_idx = 0

    # --- startup -----------------------------------------------------------

    def boot(self):
        """Show splash, wait for the drive (race-safe), scan, enforce min splash time."""
        splash_start = time.monotonic()
        self.ui.draw_splash()
        self.remote.start()

        def on_tick(_elapsed):
            self.ui.draw_splash()
            self._pump_quit_events()  # keep window responsive while waiting

        self.root = drive.wait_for_library_root(
            config.DRIVE_WAIT_TIMEOUT_S, config.DRIVE_POLL_INTERVAL_S, on_tick=on_tick
        )

        if self.root:
            self.categories = library.scan_library(self.root)

        # Honor minimum splash time regardless of how fast load was.
        while time.monotonic() - splash_start < config.SPLASH_MIN_SECONDS:
            self.ui.draw_splash()
            self._pump_quit_events()
            time.sleep(0.05)

        if not self.root:
            self.state = NO_DRIVE
        elif not self.categories:
            self.state = EMPTY
        else:
            self.state = CATEGORIES
        self.dirty = True

    # --- input -------------------------------------------------------------

    def _pump_quit_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                self.running = False

    def _collect_actions(self):
        actions = list(self.remote.drain())
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key in KEY_ACTIONS:
                    actions.append(KEY_ACTIONS[event.key])
        return actions

    # --- main loop ---------------------------------------------------------

    def run(self):
        self.boot()
        while self.running:
            for action in self._collect_actions():
                self._handle(action)

            if self.state == PLAYING:
                # VLC owns the screen; just watch for it finishing.
                if not self.player.is_running():
                    self.state = DETAIL
                    self.dirty = True
            elif self.dirty:
                self._render()
                self.dirty = False

            self.clock.tick(config.TARGET_FPS)

        self._shutdown()

    def _handle(self, action):
        # Global actions first.
        if action == "power":
            self._handle_power()
            return
        if action == "home" and self.state in (GRID, DETAIL):
            self.state = CATEGORIES
            self.dirty = True
            return

        handler = {
            NO_DRIVE: self._on_no_drive,
            EMPTY: self._on_empty,
            CATEGORIES: self._on_categories,
            GRID: self._on_grid,
            DETAIL: self._on_detail,
            PLAYING: self._on_playing,
        }.get(self.state)
        if handler:
            handler(action)

    def _handle_power(self):
        act = config.POWER_BUTTON_ACTION
        if act == "quit":
            self.running = False
        elif act == "shutdown":
            self.running = False
            import subprocess
            subprocess.Popen(["sudo", "poweroff"])
        # "ignore" -> do nothing

    # --- per-state handlers ------------------------------------------------

    def _on_no_drive(self, action):
        # Allow a manual re-scan via OK; otherwise the loop keeps showing the
        # message. (Hot-plug rescan happens on OK.)
        if action == "ok":
            self.root = drive.find_library_root()
            if self.root:
                self.categories = library.scan_library(self.root)
                self.state = CATEGORIES if self.categories else EMPTY
                self.dirty = True

    def _on_empty(self, action):
        if action == "ok":
            self.categories = library.scan_library(self.root) if self.root else []
            if self.categories:
                self.state = CATEGORIES
                self.dirty = True

    def _on_categories(self, action):
        n = len(self.categories)
        if n == 0:
            return
        if action == "up":
            self.cat_idx = (self.cat_idx - 1) % n
            self.dirty = True
        elif action == "down":
            self.cat_idx = (self.cat_idx + 1) % n
            self.dirty = True
        elif action in ("ok", "right", "play_pause"):
            self.grid_idx = 0
            self.grid_scroll = 0
            self.state = GRID
            self.dirty = True

    def _on_grid(self, action):
        cat = self.categories[self.cat_idx]
        n = len(cat.items)
        cols = config.GRID_COLUMNS
        if n == 0:
            if action == "back":
                self.state = CATEGORIES
                self.dirty = True
            return

        if action == "left":
            self.grid_idx = (self.grid_idx - 1) % n
        elif action == "right":
            self.grid_idx = (self.grid_idx + 1) % n
        elif action == "up":
            self.grid_idx = self.grid_idx - cols if self.grid_idx - cols >= 0 else self.grid_idx
        elif action == "down":
            self.grid_idx = self.grid_idx + cols if self.grid_idx + cols < n else self.grid_idx
        elif action == "back":
            self.state = CATEGORIES
            self.dirty = True
            return
        elif action in ("ok", "play_pause"):
            self.episode_idx = 0
            self.state = DETAIL
            self.dirty = True
            return
        else:
            return

        self._rescroll_grid()
        self.dirty = True

    def _rescroll_grid(self):
        cols = config.GRID_COLUMNS
        cell_h = config.COVER_H + self.ui.font_small.get_height() + 8
        visible_rows = max(1, (self.ui.h - config.GRID_TOP - 40) // (cell_h + config.GRID_V_SPACING))
        row = self.grid_idx // cols
        if row < self.grid_scroll:
            self.grid_scroll = row
        elif row >= self.grid_scroll + visible_rows:
            self.grid_scroll = row - visible_rows + 1

    def _current_item(self):
        return self.categories[self.cat_idx].items[self.grid_idx]

    def _on_detail(self, action):
        item = self._current_item()
        if action == "back":
            self.state = GRID
            self.dirty = True
        elif action == "up" and len(item.videos) > 1:
            self.episode_idx = (self.episode_idx - 1) % len(item.videos)
            self.dirty = True
        elif action == "down" and len(item.videos) > 1:
            self.episode_idx = (self.episode_idx + 1) % len(item.videos)
            self.dirty = True
        elif action in ("ok", "play_pause"):
            if item.has_video:
                idx = self.episode_idx if self.episode_idx < len(item.videos) else 0
                self.player.play(item.videos[idx])
                self.state = PLAYING

    def _on_playing(self, action):
        if action == "play_pause":
            self.player.toggle_pause()
        elif action == "back":
            self.player.stop()
            self.state = DETAIL
            self.dirty = True
        elif action == "vol_up":
            self.player.vol_up()
        elif action == "vol_down":
            self.player.vol_down()
        elif action == "mute":
            self.player.toggle_mute()

    # --- render ------------------------------------------------------------

    def _render(self):
        if self.state == NO_DRIVE:
            self.ui.draw_message("No drive found",
                                 "Insert a USB drive and press OK")
        elif self.state == EMPTY:
            self.ui.draw_message("No media found",
                                 "Drive detected but no playable titles. Press OK to rescan.")
        elif self.state == CATEGORIES:
            self.ui.draw_categories(self.categories, self.cat_idx)
        elif self.state == GRID:
            self.ui.draw_grid(self.categories[self.cat_idx], self.grid_idx, self.grid_scroll)
        elif self.state == DETAIL:
            self.ui.draw_detail(self._current_item(), self.episode_idx)

    def _shutdown(self):
        try:
            self.player.stop()
        finally:
            self.remote.stop()
            pygame.quit()


def main():
    app = Jimflix()
    try:
        app.run()
    except KeyboardInterrupt:
        app._shutdown()
        sys.exit(0)


if __name__ == "__main__":
    main()
