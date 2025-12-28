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
        self.apply_order = 0
        self.volume_db = 0
        self.overwritten_ranges = []
    
    def set_base(self):
        if self.versions:
            return
        self.versions.append("__COMPUTED_BASE__")
        self.version_params.append(None)
        self.has_base = True
        self.active_idx = 0
    
    def add_version(self, audio_data, params=None):
        import soundfile as sf
        real_versions = [v for v in self.versions if v not in ("__COMPUTED_BASE__", "__SILENT__")]
        idx = len(real_versions)
        path = os.path.join(self.parts_dir, f"{self.id}_v{idx}.wav")
        sf.write(path, audio_data, self.sr)
        self.versions.append(path)
        self.version_params.append(params)
        self.active_idx = len(self.versions) - 1
        return self.active_idx
    
    def add_silent_version(self, params=None):
        self.versions.append("__SILENT__")
        self.version_params.append(params or {"silent": True})
        self.active_idx = len(self.versions) - 1
        return self.active_idx
    
    def get_data(self, idx=None):
        if idx is None:
            idx = self.active_idx
        if not self.versions or idx >= len(self.versions):
            return None
        
        path = self.versions[idx]
        if path == "__COMPUTED_BASE__":
            return None
        
        if path == "__SILENT__":
            return np.zeros(self.end - self.start, dtype=np.float32)
        
        if path and os.path.exists(path):
            import soundfile as sf
            data, _ = sf.read(path)
            return data.astype(np.float32)
        return None
    
    def get_base_data(self):
        return None
    
    def to_dict(self):
        versions_out = []
        for v in self.versions:
            if v in ("__COMPUTED_BASE__", "__SILENT__"):
                versions_out.append(v)
            else:
                versions_out.append(os.path.basename(v))
        return {
            "id": self.id, "start": self.start, "end": self.end,
            "active_idx": self.active_idx, "has_base": self.has_base,
            "versions": versions_out,
            "version_params": self.version_params,
            "last_blend": self.last_blend,
            "last_preserve": self.last_preserve,
            "apply_order": self.apply_order,
            "volume_db": self.volume_db
        }
    
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
        self.versions.pop(self.active_idx)
        self.version_params.pop(self.active_idx)
        self.active_idx = min(self.active_idx, len(self.versions) - 1)
        return True
    
    def delete_others(self):
        if len(self.versions) <= 1:
            return
        keep_path = self.versions[self.active_idx]
        keep_params = self.version_params[self.active_idx]
        self.versions = [keep_path]
        self.version_params = [keep_params]
        self.active_idx = 0
        self.has_base = False
    
    def cleanup(self):
        for p in self.versions:
            if p not in ("__COMPUTED_BASE__", "__SILENT__"):
                try: os.remove(p)
                except: pass
        self.versions = []
        self.version_params = []
    
    def version_count(self):
        return len(self.versions) - (1 if self.has_base else 0)
    
    def version_label(self, idx):
        if self.has_base and idx == 0:
            return tr("Original")
        path = self.versions[idx] if idx < len(self.versions) else ""
        offset = 1 if self.has_base else 0
        if path == "__SILENT__":
            return f"{tr('Silent')} {idx - offset + 1}"
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