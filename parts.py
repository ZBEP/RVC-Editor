import os
import uuid
import time
import numpy as np

from lang import tr


class PartGroup:
    
    def __init__(self, start, end, parts_dir, sr):
        self.id = uuid.uuid4().hex[:8]
        self.start = start
        self.end = end
        self.parts_dir = parts_dir
        self.sr = sr
        self.versions = []
        self.version_params = []
        self.active_idx = 0
        self.level = 0
        self.has_base = False
        self.created_at = time.time()
        self.last_blend = 0
        self.last_preserve = True
    
    def set_base(self, audio_data):
        if self.versions:
            return
        import soundfile as sf
        path = os.path.join(self.parts_dir, f"{self.id}_base.wav")
        sf.write(path, audio_data, self.sr)
        self.versions.append(path)
        self.version_params.append(None)
        self.has_base = True
        self.active_idx = 0
    
    def add_version(self, audio_data, params=None):
        import soundfile as sf
        idx = len(self.versions)
        path = os.path.join(self.parts_dir, f"{self.id}_v{idx}.wav")
        sf.write(path, audio_data, self.sr)
        self.versions.append(path)
        self.version_params.append(params)
        self.active_idx = len(self.versions) - 1
        return self.active_idx
    
    def get_data(self, idx=None):
        if idx is None:
            idx = self.active_idx
        if not self.versions or idx >= len(self.versions):
            return None
        import soundfile as sf
        path = self.versions[idx]
        if os.path.exists(path):
            data, _ = sf.read(path)
            return data.astype(np.float32)
        return None
    
    def get_base_data(self):
        return self.get_data(0) if self.has_base and self.versions else None
    
    def get_params(self, idx=None):
        if idx is None:
            idx = self.active_idx
        return self.version_params[idx] if idx < len(self.version_params) else None
    
    def switch(self, delta):
        if len(self.versions) <= 1:
            return False
        new_idx = (self.active_idx + delta) % len(self.versions)
        if new_idx != self.active_idx:
            self.active_idx = new_idx
            return True
        return False
    
    def delete_current(self):
        if len(self.versions) <= 1:
            return False
        if self.has_base and self.active_idx == 0 and len(self.versions) == 2:
            return False
        path = self.versions.pop(self.active_idx)
        self.version_params.pop(self.active_idx)
        try: os.remove(path)
        except: pass
        self.active_idx = min(self.active_idx, len(self.versions) - 1)
        return True
    
    def delete_others(self):
        if len(self.versions) <= 1:
            return
        keep_path = self.versions[self.active_idx]
        keep_params = self.version_params[self.active_idx]
        for p in self.versions:
            if p != keep_path:
                try: os.remove(p)
                except: pass
        self.versions = [keep_path]
        self.version_params = [keep_params]
        self.active_idx = 0
        self.has_base = False
    
    def cleanup(self):
        for p in self.versions:
            try: os.remove(p)
            except: pass
        self.versions = []
        self.version_params = []
    
    def version_count(self):
        return len(self.versions) - (1 if self.has_base else 0)
    
    def version_label(self, idx):
        if self.has_base and idx == 0:
            return tr("Original")
        offset = 1 if self.has_base else 0
        return f"{tr('Version')} {idx - offset + 1}"
    
    def format_params(self, idx):
        params = self.get_params(idx)
        if not params:
            return ""
        F0_SHORT = {"rmvpe": "RM", "mangio-crepe": "MC", "mangio-crepe-tiny": "MCt",
                    "crepe": "CR", "crepe-tiny": "CRt", "harvest": "HV", "pm": "PM"}
        def fmt(v): return f"{v:.2f}".lstrip('0') or '0'
        f0 = F0_SHORT.get(params.get("f0_method", ""), "?")
        parts = [f0, f"I{fmt(params.get('index_rate', .9))}",
                 f"P{fmt(params.get('protect', .33))}", f"F{params.get('filter_radius', 3)}"]
        if "crepe" in params.get("f0_method", ""):
            parts.append(f"H{params.get('crepe_hop_length', 120)}")
        source_mode = params.get("source_mode", "")
        if source_mode:
            parts.append(f"- {source_mode}")
        return " ".join(parts)
    
    def size(self):
        return self.end - self.start
    
    def to_dict(self):
        return {
            "id": self.id, "start": self.start, "end": self.end,
            "active_idx": self.active_idx, "has_base": self.has_base,
            "versions": [os.path.basename(v) for v in self.versions],
            "version_params": self.version_params,
            "last_blend": self.last_blend,
            "last_preserve": self.last_preserve
        }