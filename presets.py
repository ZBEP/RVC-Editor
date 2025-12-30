import os
import json

from lang import tr

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PRESETS_FILE = os.path.join(APP_DIR, "presets.json")

PRESET_KEYS = [f"F{i}" for i in range(1, 13)]

DEFAULT_PRESET_VALUES = [
    # F1-F7: rmvpe
    {"f0_method": "rmvpe", "index_rate": 0.9, "protect": 0.33, "filter_radius": 3, "resample_sr": 0, "rms_mix_rate": 0.25, "crepe_hop_length": 120},
    {"f0_method": "rmvpe", "index_rate": 0.9, "protect": 0.5, "filter_radius": 3, "resample_sr": 0, "rms_mix_rate": 0.25, "crepe_hop_length": 120},
    {"f0_method": "rmvpe", "index_rate": 0.9, "protect": 0.0, "filter_radius": 3, "resample_sr": 0, "rms_mix_rate": 0.25, "crepe_hop_length": 120},
    {"f0_method": "rmvpe", "index_rate": 0.5, "protect": 0.5, "filter_radius": 3, "resample_sr": 0, "rms_mix_rate": 0.25, "crepe_hop_length": 120},
    {"f0_method": "rmvpe", "index_rate": 0.01, "protect": 0.01, "filter_radius": 3, "resample_sr": 0, "rms_mix_rate": 0.25, "crepe_hop_length": 120},
    {"f0_method": "rmvpe", "index_rate": 0.2, "protect": 0.0, "filter_radius": 3, "resample_sr": 0, "rms_mix_rate": 0.25, "crepe_hop_length": 120},
    {"f0_method": "rmvpe", "index_rate": 0.2, "protect": 0.01, "filter_radius": 3, "resample_sr": 0, "rms_mix_rate": 0.25, "crepe_hop_length": 120},
    # F8-F11: mangio-crepe
    {"f0_method": "mangio-crepe", "index_rate": 0.9, "protect": 0.33, "filter_radius": 3, "resample_sr": 0, "rms_mix_rate": 0.25, "crepe_hop_length": 120},
    {"f0_method": "mangio-crepe", "index_rate": 0.01, "protect": 0.01, "filter_radius": 3, "resample_sr": 0, "rms_mix_rate": 0.25, "crepe_hop_length": 120},
    {"f0_method": "mangio-crepe", "index_rate": 0.9, "protect": 0.33, "filter_radius": 3, "resample_sr": 0, "rms_mix_rate": 0.25, "crepe_hop_length": 512},
    {"f0_method": "mangio-crepe", "index_rate": 0.01, "protect": 0.01, "filter_radius": 3, "resample_sr": 0, "rms_mix_rate": 0.25, "crepe_hop_length": 512},
]


def get_default_presets():
    presets = {}
    for i, preset_data in enumerate(DEFAULT_PRESET_VALUES):
        key = f"F{i + 1}"
        presets[key] = {
            "model": "",
            "index": "",
            "pitch": 0,
            "f0_method": preset_data.get("f0_method", "rmvpe"),
            "index_rate": preset_data["index_rate"],
            "filter_radius": preset_data["filter_radius"],
            "resample_sr": preset_data["resample_sr"],
            "rms_mix_rate": preset_data["rms_mix_rate"],
            "protect": preset_data["protect"],
            "crepe_hop_length": preset_data["crepe_hop_length"],
            "output_format": "wav"
        }
    return presets


def load_presets():
    if os.path.exists(PRESETS_FILE):
        try:
            with open(PRESETS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return get_default_presets()


def save_presets(presets):
    try:
        with open(PRESETS_FILE, 'w', encoding='utf-8') as f:
            json.dump(presets, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"{tr('Preset save error:')} {e}")