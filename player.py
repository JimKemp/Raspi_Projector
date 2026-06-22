"""
Plays a single video fullscreen via VLC (cvlc) and controls it over VLC's
"rc" (remote control) socket. Running VLC as a subprocess keeps it from
fighting pygame for the display -- it takes the screen for one file, then
hands control back when stopped or finished.
"""

import socket
import subprocess
import time

import config


class Player:
    def __init__(self):
        self.proc = None
        self.sock = None
        self.volume = config.VLC_VOLUME_START
        self._muted = False
        self._premute_volume = config.VLC_VOLUME_START

    # --- lifecycle ---------------------------------------------------------

    def play(self, filepath):
        """Launch VLC fullscreen for filepath and connect to its rc socket."""
        self.stop()  # ensure nothing else is running
        cmd = [
            "cvlc",
            "--fullscreen",
            "--no-video-title-show",
            "--play-and-exit",
            "--intf", "rc",
            "--rc-host", f"{config.VLC_RC_HOST}:{config.VLC_RC_PORT}",
            filepath,
        ]
        self.proc = subprocess.Popen(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        self._connect()
        self._muted = False
        self._set_volume(self.volume)

    def stop(self):
        if self.sock:
            self._send("quit")
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None
        if self.proc:
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            self.proc = None

    def is_running(self):
        return self.proc is not None and self.proc.poll() is None

    # --- controls ----------------------------------------------------------

    def toggle_pause(self):
        self._send("pause")

    def vol_up(self):
        self._muted = False
        self.volume = min(config.VLC_VOLUME_MAX, self.volume + config.VLC_VOLUME_STEP)
        self._set_volume(self.volume)

    def vol_down(self):
        self._muted = False
        self.volume = max(0, self.volume - config.VLC_VOLUME_STEP)
        self._set_volume(self.volume)

    def toggle_mute(self):
        # VLC's rc interface has no mute command, so emulate it by setting
        # volume to 0 and restoring the previous level.
        if self._muted:
            self._muted = False
            self.volume = self._premute_volume
            self._set_volume(self.volume)
        else:
            self._muted = True
            self._premute_volume = self.volume
            self._set_volume(0)

    # --- internals ---------------------------------------------------------

    def _connect(self, retries=20, delay=0.25):
        for _ in range(retries):
            try:
                self.sock = socket.create_connection(
                    (config.VLC_RC_HOST, config.VLC_RC_PORT), timeout=1
                )
                self.sock.settimeout(1)
                return True
            except (ConnectionRefusedError, OSError):
                time.sleep(delay)
        self.sock = None
        return False

    def _send(self, command):
        if not self.sock:
            return
        try:
            self.sock.sendall((command + "\n").encode())
        except OSError:
            pass

    def _set_volume(self, level):
        self._send(f"volume {int(level)}")
