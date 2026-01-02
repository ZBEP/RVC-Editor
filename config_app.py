import os
import sys
import json

APP_DIR = os.path.dirname(os.path.abspath(__file__))
RVC_ROOT = os.path.dirname(APP_DIR)

if RVC_ROOT not in sys.path:
    sys.path.insert(0, RVC_ROOT)

os.environ["RVC_ROOT"] = RVC_ROOT

WEIGHTS_DIR = os.path.join(RVC_ROOT, "assets", "weights")
LOGS_DIR = os.path.join(RVC_ROOT, "logs")
INDEX_ROOT = os.path.join(RVC_ROOT, "logs")

INPUT_DIR = os.path.join(APP_DIR, "input")
OUTPUT_DIR = os.path.join(APP_DIR, "output")
TEMP_DIR = os.path.join(APP_DIR, "temp")
SETTINGS_FILE = os.path.join(APP_DIR, "settings.json")

os.makedirs(INPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

DEFAULT_SETTINGS = {
    "model": "",
    "index": "",
    "input_dir": INPUT_DIR,
    "output_dir": OUTPUT_DIR,
    "pitch": 0,
    "f0_method": "rmvpe",
    "index_rate": 0.90,
    "filter_radius": 3,
    "resample_sr": 0,
    "rms_mix_rate": 0.25,
    "protect": 0.33,
    "crepe_hop_length": 120,
    "output_format": "wav",
    "log_visible": False,
    "window_geometry": "",
    "window_state": "normal",
    "editor_file": "",
    "preset_load_model": False,
    "preset_load_pitch": False,
    "preset_load_f0": False,
    "blend_mode": 0,
    "crossfade_type": 0,
}

AUDIO_EXTENSIONS = ('.wav', '.mp3', '.flac', '.ogg', '.m4a', '.wma', '.aac')

AUDIO_FORMATS = [
    ("Audio Files", "*.wav *.mp3 *.flac *.ogg *.m4a *.wma *.aac"),
    ("WAV files", "*.wav"),
    ("MP3 files", "*.mp3"),
    ("FLAC files", "*.flac"),
    ("All files", "*.*")
]

OUTPUT_FORMATS = ["wav", "flac", "mp3", "m4a"]

F0_METHODS = ["pm", "harvest", "crepe", "crepe-tiny", "mangio-crepe", "mangio-crepe-tiny", "rmvpe"]

CREPE_METHODS_WITH_HOP = ["mangio-crepe", "mangio-crepe-tiny"]


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                settings = DEFAULT_SETTINGS.copy()
                settings.update(saved)
                return settings
        except Exception as e:
            print(f"Settings load error: {e}")
    return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Settings save error: {e}")