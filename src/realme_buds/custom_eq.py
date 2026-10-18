from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

DEFAULT_FREQUENCIES = (64, 250, 1000, 4000, 8000, 16000)
_BASE_CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
CONFIG_DIR = _BASE_CONFIG_DIR / "omarchy" / "realme-buds"
CONFIG_PATH = CONFIG_DIR / "custom_eq.json"
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
LEGACY_CONFIG_PATHS = (
    _PLUGIN_ROOT / "custom_eq.json",
    _BASE_CONFIG_DIR / "omarchy" / "plugins" / "realme-buds.control" / "custom_eq.json",
)


@dataclass(frozen=True)
class CustomEqBand:
    frequency: int
    gain_db: int


@dataclass(frozen=True)
class CustomEqPreset:
    id: int
    name: str
    bands: tuple[CustomEqBand, ...]
    base_preset: str = "balanced"

    def to_dict(self) -> dict[str, object]:
        return {
            "eq_id": self.id,
            "name": self.name,
            "minimum_gain_db": -12,
            "maximum_gain_db": 12,
            "gain_step_db": 1,
            "bands": [{"frequency": b.frequency, "gain_db": b.gain_db} for b in self.bands],
            "base_preset": self.base_preset,
        }

    def infer_base_preset(self) -> str:
        """Infer best matching hardware preset from band gains."""
        if not self.bands:
            return "balanced"
        gains = [b.gain_db for b in self.bands]
        # Low frequencies: bands 0, 1
        low = sum(gains[:2]) / 2.0
        # Mid frequencies: bands 2, 3
        mid = sum(gains[2:4]) / 2.0
        # High frequencies: bands 4, 5
        high = sum(gains[4:]) / 2.0

        if low > mid and low > high and low > 1:
            return "bass"
        elif mid > low and mid > high and mid > 1:
            return "vocals"
        elif high > low and high > mid and high > 1:
            return "bright"
        return "balanced"


class CustomEqStore:
    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path else CONFIG_PATH

    def _default_data(self) -> dict[str, object]:
        return {
            "active_id": 100,
            "presets": [
                {
                    "id": 100,
                    "name": "Custom Profile",
                    "base_preset": "balanced",
                    "bands": [{"frequency": f, "gain_db": 0} for f in DEFAULT_FREQUENCIES],
                },
                {
                    "id": 101,
                    "name": "Bass & Treble",
                    "base_preset": "bass",
                    "bands": [
                        {"frequency": 64, "gain_db": 4},
                        {"frequency": 250, "gain_db": 2},
                        {"frequency": 1000, "gain_db": 0},
                        {"frequency": 4000, "gain_db": 1},
                        {"frequency": 8000, "gain_db": 3},
                        {"frequency": 16000, "gain_db": 4},
                    ],
                },
                {
                    "id": 102,
                    "name": "Vocal Boost",
                    "base_preset": "vocals",
                    "bands": [
                        {"frequency": 64, "gain_db": -1},
                        {"frequency": 250, "gain_db": 0},
                        {"frequency": 1000, "gain_db": 3},
                        {"frequency": 4000, "gain_db": 4},
                        {"frequency": 8000, "gain_db": 2},
                        {"frequency": 16000, "gain_db": 0},
                    ],
                },
                {
                    "id": 103,
                    "name": "Deep Bass",
                    "base_preset": "bass",
                    "bands": [
                        {"frequency": 64, "gain_db": 6},
                        {"frequency": 250, "gain_db": 4},
                        {"frequency": 1000, "gain_db": 1},
                        {"frequency": 4000, "gain_db": 0},
                        {"frequency": 8000, "gain_db": 0},
                        {"frequency": 16000, "gain_db": 0},
                    ],
                },
            ],
        }

    def load(self) -> dict[str, object]:
        if not self.path.exists() and self.path == CONFIG_PATH:
            for legacy_path in LEGACY_CONFIG_PATHS:
                if legacy_path.exists():
                    try:
                        data = json.loads(legacy_path.read_text(encoding="utf-8"))
                        self.save(data)
                        legacy_path.unlink(missing_ok=True)
                        return data
                    except Exception:
                        pass
        if not self.path.exists():
            return self._default_data()
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and "presets" in data:
                    return data
        except Exception:
            pass
        return self._default_data()

    def save(self, data: dict[str, object]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            if self.path == CONFIG_PATH:
                for legacy_path in LEGACY_CONFIG_PATHS:
                    if legacy_path.exists():
                        legacy_path.unlink(missing_ok=True)
        except Exception:
            pass

    def list_presets(self) -> list[CustomEqPreset]:
        data = self.load()
        presets_data = data.get("presets", [])
        presets: list[CustomEqPreset] = []
        for p in presets_data:
            if not isinstance(p, dict):
                continue
            bands_data = p.get("bands", [])
            bands = []
            for b in bands_data:
                if isinstance(b, dict):
                    bands.append(CustomEqBand(int(b.get("frequency", 1000)), int(b.get("gain_db", 0))))
            presets.append(
                CustomEqPreset(
                    id=int(p.get("id", 100)),
                    name=str(p.get("name", "Custom")),
                    bands=tuple(bands),
                    base_preset=str(p.get("base_preset", "balanced")),
                )
            )
        return presets

    def get_preset(self, identifier: int | str) -> CustomEqPreset | None:
        presets = self.list_presets()
        if isinstance(identifier, int):
            for p in presets:
                if p.id == identifier:
                    return p
        identifier_str = str(identifier).strip().lower()
        for p in presets:
            if str(p.id) == identifier_str or p.name.lower() == identifier_str:
                return p
        return None

    def get_active_id(self) -> int:
        data = self.load()
        return int(data.get("active_id", 100))

    def set_active_id(self, preset_id: int) -> None:
        data = self.load()
        data["active_id"] = preset_id
        self.save(data)

    def add_preset(
        self,
        name: str,
        gains: Sequence[int] | None = None,
        base_preset: str = "balanced",
    ) -> CustomEqPreset:
        data = self.load()
        presets = data.get("presets", [])
        existing_ids = [p["id"] for p in presets if isinstance(p, dict) and "id" in p]
        next_id = max(existing_ids, default=99) + 1
        if next_id < 100:
            next_id = 100

        bands_list = []
        gains_seq = list(gains) if gains is not None else [0] * len(DEFAULT_FREQUENCIES)
        for i, freq in enumerate(DEFAULT_FREQUENCIES):
            gain = max(-12, min(12, int(gains_seq[i]) if i < len(gains_seq) else 0))
            bands_list.append({"frequency": freq, "gain_db": gain})

        new_preset = {
            "id": next_id,
            "name": name.strip() or f"Custom {next_id - 99}",
            "base_preset": base_preset,
            "bands": bands_list,
        }
        presets.append(new_preset)
        data["presets"] = presets
        data["active_id"] = next_id
        self.save(data)
        return self.get_preset(next_id) or CustomEqPreset(
            id=next_id,
            name=new_preset["name"],
            bands=tuple(CustomEqBand(b["frequency"], b["gain_db"]) for b in bands_list),
            base_preset=base_preset,
        )

    def update_preset(
        self,
        preset_id: int,
        name: str | None = None,
        gains: Sequence[int] | None = None,
        base_preset: str | None = None,
    ) -> CustomEqPreset | None:
        data = self.load()
        presets = data.get("presets", [])
        target = None
        for p in presets:
            if isinstance(p, dict) and p.get("id") == preset_id:
                target = p
                break
        if target is None:
            return None

        if name is not None:
            target["name"] = name.strip()
        if base_preset is not None:
            target["base_preset"] = base_preset

        if gains is not None:
            bands_list = []
            for i, freq in enumerate(DEFAULT_FREQUENCIES):
                gain = max(-12, min(12, int(gains[i]) if i < len(gains) else 0))
                bands_list.append({"frequency": freq, "gain_db": gain})
            target["bands"] = bands_list

        data["presets"] = presets
        data["active_id"] = preset_id
        self.save(data)
        return self.get_preset(preset_id)

    def delete_preset(self, preset_id: int) -> bool:
        data = self.load()
        presets = [p for p in data.get("presets", []) if isinstance(p, dict) and p.get("id") != preset_id]
        if not presets:
            # Always keep at least one preset
            presets = self._default_data()["presets"]
        data["presets"] = presets
        if data.get("active_id") == preset_id:
            data["active_id"] = presets[0]["id"]
        self.save(data)
        return True
