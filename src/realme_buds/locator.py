import io
import math
import os
import shutil
import struct
import subprocess
import tempfile
import threading
import time
import wave
from typing import Any, Dict, Optional


def find_bluetooth_sink(address: Optional[str] = None) -> Optional[str]:
    """Find the PipeWire/PulseAudio sink name for a Bluetooth device address."""
    addr_slug = address.upper().replace(":", "_") if address else None
    
    # 1. Try pactl list short sinks
    if shutil.which("pactl"):
        try:
            res = subprocess.run(["pactl", "list", "short", "sinks"], capture_output=True, text=True, timeout=1.5)
            if res.returncode == 0:
                for line in res.stdout.strip().splitlines():
                    parts = line.split()
                    if len(parts) >= 2:
                        name = parts[1]
                        if addr_slug and addr_slug in name:
                            return name
                        if not addr_slug and "bluez_output" in name:
                            return name
        except Exception:
            pass

    # 2. Try wpctl status
    if shutil.which("wpctl"):
        try:
            res = subprocess.run(["wpctl", "status"], capture_output=True, text=True, timeout=1.5)
            if res.returncode == 0 and addr_slug:
                for line in res.stdout.splitlines():
                    if addr_slug in line or "bluez_output" in line:
                        for token in line.split():
                            if "bluez_output" in token:
                                return token.strip()
        except Exception:
            pass

    return None


def generate_locator_wav(duration: float = 2.0, sample_rate: int = 44100, channel: str = "both") -> bytes:
    """Synthesize a loud acoustic locator chirp WAV (2.2kHz -> 3.8kHz sweep).
    
    channel can be 'left', 'right', or 'both'.
    """
    num_samples = int(duration * sample_rate)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)

        frames = bytearray()
        period = 0.25  # 250ms total cycle: 180ms chirp sweep, 70ms silence
        chirp_len = 0.18
        f_start = 2200.0
        f_end = 3800.0
        f_slope = (f_end - f_start) / chirp_len

        for i in range(num_samples):
            t = i / sample_rate
            cycle_t = t % period

            if cycle_t < chirp_len:
                # Linear frequency sweep with continuous phase integration
                phase = 2.0 * math.pi * (f_start * cycle_t + 0.5 * f_slope * (cycle_t**2))

                # Smooth envelope (8ms attack/decay) to prevent clicks
                envelope = 1.0
                attack = 0.008
                if cycle_t < attack:
                    envelope = 0.5 * (1.0 - math.cos(math.pi * cycle_t / attack))
                elif cycle_t > (chirp_len - attack):
                    decay_t = chirp_len - cycle_t
                    envelope = 0.5 * (1.0 - math.cos(math.pi * decay_t / attack))

                # Loud volume (near full 16-bit range)
                val = int(28500.0 * envelope * math.sin(phase))
            else:
                val = 0

            left_sample = val if channel in ("left", "both") else 0
            right_sample = val if channel in ("right", "both") else 0
            frames.extend(struct.pack("<hh", left_sample, right_sample))

        wf.writeframes(frames)

    return buffer.getvalue()


class AcousticLocator:
    """Manages playing localized acoustic locator chimes to find misplaced earbuds."""

    def __init__(self, default_address: Optional[str] = None):
        self.default_address = default_address
        self._lock = threading.Lock()
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._current_target: Optional[str] = None
        self._start_time: float = 0.0
        self._duration: float = 30.0
        self._tmp_file: Optional[str] = None

    @property
    def is_ringing(self) -> bool:
        with self._lock:
            return self._current_target is not None and not self._stop_event.is_set()

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            ringing = self._current_target is not None and not self._stop_event.is_set()
            elapsed = round(time.time() - self._start_time, 1) if ringing else 0.0
            return {
                "ringing": ringing,
                "target": self._current_target if ringing else None,
                "elapsed_seconds": elapsed,
                "max_duration": self._duration,
            }

    def start(
        self,
        target: str = "both",
        duration: float = 30.0,
        address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Start playing locator chime on target ('left', 'right', 'both')."""
        target = target.lower()
        if target not in ("left", "right", "both"):
            raise ValueError(f"Invalid target: {target!r}. Must be 'left', 'right', or 'both'")

        self.stop()

        with self._lock:
            self._current_target = target
            self._duration = duration
            self._start_time = time.time()
            self._stop_event.clear()

            # Generate chirp file
            wav_bytes = generate_locator_wav(duration=2.0, channel=target)
            fd, tmp_path = tempfile.mkstemp(prefix=f"realme_locate_{target}_", suffix=".wav")
            os.write(fd, wav_bytes)
            os.close(fd)
            self._tmp_file = tmp_path

            # Launch background worker
            self._thread = threading.Thread(
                target=self._worker_loop,
                args=(tmp_path, target, duration, address or self.default_address),
                daemon=True,
            )
            self._thread.start()

        return self.get_state()

    def _worker_loop(self, tmp_path: str, target: str, duration: float, address: Optional[str]) -> None:
        target_sink = find_bluetooth_sink(address)
        player_cmd: list[str] = []

        if shutil.which("pw-play"):
            player_cmd = ["pw-play"]
            if target_sink:
                player_cmd.extend(["--target", target_sink])
            player_cmd.extend(["--volume", "1.0", tmp_path])
        elif shutil.which("paplay"):
            player_cmd = ["paplay"]
            if target_sink:
                player_cmd.extend([f"--device={target_sink}"])
            player_cmd.append(tmp_path)
        elif shutil.which("aplay"):
            player_cmd = ["aplay", "-q", tmp_path]
        else:
            return

        end_time = time.time() + duration
        try:
            while not self._stop_event.is_set() and time.time() < end_time:
                proc = subprocess.Popen(player_cmd)
                with self._lock:
                    self._proc = proc
                proc.wait()
                if self._stop_event.is_set():
                    break
                time.sleep(0.05)
        finally:
            with self._lock:
                if self._proc is not None:
                    try:
                        self._proc.terminate()
                        self._proc.wait(timeout=0.2)
                    except Exception:
                        pass
                    self._proc = None
                self._current_target = None
                if self._tmp_file and os.path.exists(self._tmp_file):
                    try:
                        os.unlink(self._tmp_file)
                    except Exception:
                        pass
                    self._tmp_file = None

    def stop(self) -> Dict[str, Any]:
        """Immediately stop playing the locator chime."""
        self._stop_event.set()
        with self._lock:
            if self._proc is not None:
                try:
                    self._proc.terminate()
                    self._proc.kill()
                except Exception:
                    pass
                self._proc = None
            if self._tmp_file and os.path.exists(self._tmp_file):
                try:
                    os.unlink(self._tmp_file)
                except Exception:
                    pass
                self._tmp_file = None
            self._current_target = None

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=0.5)

        return self.get_state()
