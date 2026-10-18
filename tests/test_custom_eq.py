import tempfile
import unittest
from pathlib import Path

from realme_buds.custom_eq import (
    DEFAULT_FREQUENCIES,
    CustomEqBand,
    CustomEqPreset,
    CustomEqStore,
)


class CustomEqPresetTests(unittest.TestCase):
    def test_infer_base_preset_flat_is_balanced(self):
        preset = CustomEqPreset(
            id=100,
            name="Flat",
            bands=tuple(CustomEqBand(f, 0) for f in DEFAULT_FREQUENCIES),
        )
        self.assertEqual(preset.infer_base_preset(), "balanced")

    def test_infer_base_preset_bass_boost(self):
        # High gain in lower frequencies (64, 250 Hz)
        preset = CustomEqPreset(
            id=101,
            name="Heavy Bass",
            bands=(
                CustomEqBand(64, 6),
                CustomEqBand(250, 4),
                CustomEqBand(1000, 0),
                CustomEqBand(4000, 0),
                CustomEqBand(8000, 0),
                CustomEqBand(16000, 0),
            ),
        )
        self.assertEqual(preset.infer_base_preset(), "bass")

    def test_infer_base_preset_vocal_boost(self):
        # High gain in mid frequencies (1000, 4000 Hz)
        preset = CustomEqPreset(
            id=102,
            name="Vocals",
            bands=(
                CustomEqBand(64, -2),
                CustomEqBand(250, 0),
                CustomEqBand(1000, 4),
                CustomEqBand(4000, 5),
                CustomEqBand(8000, 1),
                CustomEqBand(16000, 0),
            ),
        )
        self.assertEqual(preset.infer_base_preset(), "vocals")

    def test_infer_base_preset_treble_boost(self):
        # High gain in high frequencies (8000, 16000 Hz)
        preset = CustomEqPreset(
            id=103,
            name="Crisp",
            bands=(
                CustomEqBand(64, 0),
                CustomEqBand(250, 0),
                CustomEqBand(1000, 1),
                CustomEqBand(4000, 2),
                CustomEqBand(8000, 5),
                CustomEqBand(16000, 6),
            ),
        )
        self.assertEqual(preset.infer_base_preset(), "bright")

    def test_to_dict_has_required_ui_fields(self):
        preset = CustomEqPreset(
            id=100,
            name="Test Preset",
            bands=tuple(CustomEqBand(f, 1) for f in DEFAULT_FREQUENCIES),
        )
        d = preset.to_dict()
        self.assertEqual(d["eq_id"], 100)
        self.assertEqual(d["name"], "Test Preset")
        self.assertEqual(d["minimum_gain_db"], -12)
        self.assertEqual(d["maximum_gain_db"], 12)
        self.assertEqual(len(d["bands"]), 6)


class CustomEqStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "custom_eq.json"
        self.store = CustomEqStore(self.config_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_defaults_created_on_first_load(self):
        presets = self.store.list_presets()
        self.assertGreaterEqual(len(presets), 3)
        self.assertEqual(presets[0].name, "Custom Profile")
        self.assertEqual(self.store.get_active_id(), 100)

    def test_add_preset(self):
        created = self.store.add_preset("My Custom EQ", [2, 3, 1, 0, -1, 4])
        self.assertEqual(created.name, "My Custom EQ")
        self.assertGreaterEqual(created.id, 103)
        self.assertEqual(self.store.get_active_id(), created.id)
        # Verify persistence
        reloaded = CustomEqStore(self.config_path).get_preset(created.id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.name, "My Custom EQ")
        self.assertEqual([b.gain_db for b in reloaded.bands], [2, 3, 1, 0, -1, 4])

    def test_update_preset(self):
        updated = self.store.update_preset(100, name="Renamed Flat", gains=[1, 1, 1, 1, 1, 1])
        self.assertIsNotNone(updated)
        self.assertEqual(updated.name, "Renamed Flat")
        self.assertEqual([b.gain_db for b in updated.bands], [1, 1, 1, 1, 1, 1])

    def test_delete_preset(self):
        self.store.add_preset("To Delete")
        initial_count = len(self.store.list_presets())
        last_id = self.store.list_presets()[-1].id
        self.store.delete_preset(last_id)
        self.assertEqual(len(self.store.list_presets()), initial_count - 1)
        self.assertIsNone(self.store.get_preset(last_id))


if __name__ == "__main__":
    unittest.main()
