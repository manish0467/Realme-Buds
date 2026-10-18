import io
import struct
import unittest
import wave
from unittest.mock import MagicMock, patch

from realme_buds.bridge import BudsFrontendBridge
from realme_buds.controller import BudsController
from realme_buds.locator import AcousticLocator, find_bluetooth_sink, generate_locator_wav
from realme_buds.backend import ring_buds, ring_status, stop_ring_buds


class LocatorWavTests(unittest.TestCase):
    def test_generate_locator_wav_structure(self):
        wav_bytes = generate_locator_wav(duration=0.5, sample_rate=44100, channel="both")
        self.assertTrue(len(wav_bytes) > 44)

        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            self.assertEqual(wf.getnchannels(), 2)
            self.assertEqual(wf.getsampwidth(), 2)
            self.assertEqual(wf.getframerate(), 44100)
            self.assertEqual(wf.getnframes(), int(0.5 * 44100))

    def test_channel_isolation(self):
        # Left only: right channel must be silent (all zero)
        left_wav = generate_locator_wav(duration=0.2, sample_rate=44100, channel="left")
        with wave.open(io.BytesIO(left_wav), "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            left_nonzero = 0
            right_nonzero = 0
            for i in range(0, len(frames), 4):
                l_val, r_val = struct.unpack("<hh", frames[i:i+4])
                if l_val != 0:
                    left_nonzero += 1
                if r_val != 0:
                    right_nonzero += 1
            self.assertTrue(left_nonzero > 0)
            self.assertEqual(right_nonzero, 0)

        # Right only: left channel must be silent (all zero)
        right_wav = generate_locator_wav(duration=0.2, sample_rate=44100, channel="right")
        with wave.open(io.BytesIO(right_wav), "rb") as wf:
            frames = wf.readframes(wf.getnframes())
            left_nonzero = 0
            right_nonzero = 0
            for i in range(0, len(frames), 4):
                l_val, r_val = struct.unpack("<hh", frames[i:i+4])
                if l_val != 0:
                    left_nonzero += 1
                if r_val != 0:
                    right_nonzero += 1
            self.assertEqual(left_nonzero, 0)
            self.assertTrue(right_nonzero > 0)


class AcousticLocatorTests(unittest.TestCase):
    def test_invalid_target_raises(self):
        locator = AcousticLocator()
        with self.assertRaises(ValueError):
            locator.start("middle")

    @patch("subprocess.Popen")
    @patch("shutil.which", return_value="/usr/bin/pw-play")
    def test_start_and_stop(self, mock_which, mock_popen):
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        locator = AcousticLocator(default_address="AA:BB:CC:DD:EE:FF")
        state = locator.start(target="left", duration=5.0)
        self.assertEqual(state["target"], "left")

        # Stop
        stop_state = locator.stop()
        self.assertFalse(stop_state["ringing"])
        self.assertIsNone(stop_state["target"])
        mock_proc.terminate.assert_called()

    def test_find_bluetooth_sink(self):
        with patch("shutil.which", return_value="/usr/bin/pactl"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="2505 alsa_output.pci-0000_00_1f.3.analog-stereo\n2520 bluez_output.84_9D_4B_82_AD_80.1\n"
                )
                sink = find_bluetooth_sink("84:9D:4B:82:AD:80")
                self.assertEqual(sink, "bluez_output.84_9D_4B_82_AD_80.1")


class BridgeLocatorTests(unittest.TestCase):
    def test_bridge_ring_commands(self):
        controller = BudsController()
        bridge = BudsFrontendBridge(emit=lambda _: None, controller=controller)
        bridge.locator = MagicMock()
        bridge.locator.start.return_value = {"ringing": True, "target": "both"}
        bridge.locator.stop.return_value = {"ringing": False, "target": None}
        bridge.locator.get_state.return_value = {"ringing": False, "target": None}

        # ring_buds
        res = bridge.execute("ring_buds", {"target": "left"})
        self.assertTrue(res["ok"])
        self.assertTrue(res["result"]["ringing"])

        # stop_ring_buds
        res = bridge.execute("stop_ring_buds")
        self.assertTrue(res["ok"])
        self.assertFalse(res["result"]["ringing"])

        # ring_status
        res = bridge.execute("ring_status")
        self.assertTrue(res["ok"])
        self.assertFalse(res["result"]["ringing"])


class BackendLocatorTests(unittest.TestCase):
    @patch("realme_buds.backend._get_locator")
    def test_backend_functions(self, mock_get_locator):
        mock_loc = MagicMock()
        mock_loc.start.return_value = {"ringing": True, "target": "both"}
        mock_loc.stop.return_value = {"ringing": False, "target": None}
        mock_loc.get_state.return_value = {"ringing": False, "target": None}
        mock_get_locator.return_value = mock_loc

        res = ring_buds("both")
        self.assertTrue(res["ringing"])

        res = stop_ring_buds()
        self.assertFalse(res["ringing"])

        res = ring_status()
        self.assertFalse(res["ringing"])


class CliLocatorTests(unittest.TestCase):
    def test_try_shell_find(self):
        from realme_buds.cli import _try_shell_find
        with patch("shutil.which", return_value="/usr/bin/omarchy-shell"):
            with patch("subprocess.run") as mock_run:
                # status
                mock_run.return_value = MagicMock(returncode=0, stdout='{"ringing": false}')
                res = _try_shell_find("status")
                self.assertEqual(res, {"ringing": False})

                # ring left
                mock_run.return_value = MagicMock(returncode=0, stdout="")
                res = _try_shell_find("left")
                self.assertEqual(res, {"ringing": True, "target": "left"})

                # stop
                mock_run.return_value = MagicMock(returncode=0, stdout="")
                res = _try_shell_find("stop")
                self.assertEqual(res, {"ringing": False, "stopped": True})


if __name__ == "__main__":
    unittest.main()
