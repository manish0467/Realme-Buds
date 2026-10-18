from __future__ import annotations

import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)


class MprisManager:
    """Controls media playback on the desktop via MPRIS D-Bus interface and playerctl fallback."""

    def __init__(self, *, enabled: bool = True):
        self.enabled = enabled
        self._auto_paused: list[str] = []

    def get_playing_players(self) -> list[str]:
        playing: list[str] = []
        try:
            import dbus  # type: ignore

            bus = dbus.SessionBus()
            for name in bus.list_names():
                if name.startswith("org.mpris.MediaPlayer2."):
                    try:
                        obj = bus.get_object(name, "/org/mpris/MediaPlayer2")
                        props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
                        status = str(props.Get("org.mpris.MediaPlayer2.Player", "PlaybackStatus"))
                        if status.lower() == "playing":
                            playing.append(str(name))
                    except Exception:
                        pass
        except Exception as error:
            logger.debug("Failed to query MPRIS players via D-Bus: %s", error)

        if not playing and shutil.which("playerctl"):
            try:
                proc = subprocess.run(
                    ["playerctl", "-l"],
                    capture_output=True,
                    text=True,
                    timeout=1.0,
                )
                if proc.returncode == 0:
                    for p in proc.stdout.strip().splitlines():
                        p = p.strip()
                        if not p:
                            continue
                        proc_status = subprocess.run(
                            ["playerctl", "-p", p, "status"],
                            capture_output=True,
                            text=True,
                            timeout=1.0,
                        )
                        if proc_status.returncode == 0 and proc_status.stdout.strip().lower() == "playing":
                            playing.append(p)
            except Exception:
                pass
        return playing

    def pause_all(self) -> list[str]:
        """Pause all currently playing media and remember paused players."""
        if not self.enabled:
            return []

        playing = self.get_playing_players()
        if not playing:
            return []

        self._auto_paused = list(playing)
        try:
            import dbus  # type: ignore

            bus = dbus.SessionBus()
            for name in playing:
                if name.startswith("org.mpris.MediaPlayer2."):
                    try:
                        obj = bus.get_object(name, "/org/mpris/MediaPlayer2")
                        player = dbus.Interface(obj, "org.mpris.MediaPlayer2.Player")
                        player.Pause()
                    except Exception:
                        pass
        except Exception:
            pass

        if shutil.which("playerctl"):
            for name in playing:
                try:
                    subprocess.run(
                        ["playerctl", "-p", name, "pause"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=1.0,
                    )
                except Exception:
                    pass

        return self._auto_paused

    def resume_paused(self) -> list[str]:
        """Resume playback for players that were auto-paused when earbuds were removed."""
        if not self.enabled or not self._auto_paused:
            return []

        resumed = list(self._auto_paused)
        self._auto_paused.clear()

        try:
            import dbus  # type: ignore

            bus = dbus.SessionBus()
            for name in resumed:
                if name.startswith("org.mpris.MediaPlayer2."):
                    try:
                        obj = bus.get_object(name, "/org/mpris/MediaPlayer2")
                        player = dbus.Interface(obj, "org.mpris.MediaPlayer2.Player")
                        player.Play()
                    except Exception:
                        pass
        except Exception:
            pass

        if shutil.which("playerctl"):
            for name in resumed:
                try:
                    subprocess.run(
                        ["playerctl", "-p", name, "play"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=1.0,
                    )
                except Exception:
                    pass

        return resumed

    def handle_wear_change(self, wearing: bool) -> list[str]:
        """React to earbud in-ear detection transition."""
        if not self.enabled:
            return []
        if not wearing:
            return self.pause_all()
        return self.resume_paused()

    def get_state(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "auto_paused": list(self._auto_paused),
        }
