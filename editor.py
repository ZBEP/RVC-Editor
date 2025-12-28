import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import threading
import time
import json

from lang import tr
from parts import PartGroup
from waveform import WaveformCanvas, PART_ROW_HEIGHT, PART_TOP_MARGIN
from history import HistoryManager

SNAP_THRESHOLD_PX = 10
BLEND_VALUES = [0, 15, 30, 60, 120]
CONVERT_PADDING_MS = 128


class EditorTab:
    
    def __init__(self, parent, get_converter_fn, log_fn, set_progress_fn, 
                 get_output_dir_fn, get_editor_file_fn, set_editor_file_fn,
                 get_preset_info_fn=None, initial_blend_mode=0, initial_crossfade_type=0):
        self.parent = parent
        self.get_converter = get_converter_fn
        self.log = log_fn
        self.set_progress = set_progress_fn
        self.get_output_dir = get_output_dir_fn
        self.get_editor_file = get_editor_file_fn
        self.set_editor_file = set_editor_file_fn
        self.get_preset_info = get_preset_info_fn or (lambda: {})
        
        self.source_path = None
        self.source_audio = None # Обязатено использовать в качестве источника данных для конвертации - source_audio
        self.result_audio = None
        self.source_audio_display = None # Используется только для отрисовки - source_audio_display
        self.result_audio_display = None
        
        self.sr = None
        self.total_samples = 0
        self.is_stereo = False
        
        self.zoom = 1.0
        self.offset = 0
        self.sel_start = None
        self.sel_end = None
        self.cursor_pos = None
        self.play_pos = None
        
        self.part_groups = []
        self.markers = []
        
        self._drag_mode = None
        self._active_track = 'source'
        
        self._stream = None
        self._is_playing = False
        self._play_pos = 0
        self._play_start = 0
        self._play_end = 0
        self._stream_active = False
        self._is_converting = False
        self._apply_counter = 0
        self.blend_mode = initial_blend_mode
        self.crossfade_type = initial_crossfade_type
        self.history = None
        self.source_mode = "F"
        self.output_device = None
        self.output_devices = []
        
        self._build()
        self._scan_devices()
        
        parent.winfo_toplevel().bind('<KeyPress>', self._on_key_press)

    def _init_history(self):
        project_dir = self._get_project_dir()
        if project_dir:
            os.makedirs(project_dir, exist_ok=True)
            self.history = HistoryManager(project_dir, self.sr or 44100)
            if len(self.history.snapshots) == 0:
                self._push_snapshot()
    
    def _find_part_by_id(self, part_id):
        for g in self.part_groups:
            if g.id == part_id:
                return g
        return None
    
    def _rebuild_result_from_parts(self):
        if self.source_audio is None or self.total_samples == 0:
            return
        
        self.result_audio = np.zeros(self.total_samples, dtype=np.float32)
        self.result_audio_display = np.zeros(self.total_samples, dtype=np.float32)
        
        self._assign_levels()
        sorted_parts = sorted(self.part_groups, key=lambda p: p.apply_order)
        
        for part in sorted_parts:
            self._apply_version_data(part, part.last_preserve, part.last_blend)
        
        self._compute_overwritten_ranges()
    
    def _create_snapshot(self):
        return {
            "parts": [g.to_dict() for g in self.part_groups],
            "markers": self.markers[:]
        }
    
    def _push_snapshot(self):
        if self.history:
            self.history.push(self._create_snapshot())
    
    def _restore_snapshot(self, snapshot):
        if not snapshot:
            return False
        
        self.markers = snapshot.get("markers", [])[:]
        
        parts_dir = self._get_parts_dir()
        new_ids = {p["id"] for p in snapshot.get("parts", [])}
        
        self.part_groups = [g for g in self.part_groups if g.id in new_ids]
        
        for p in snapshot.get("parts", []):
            existing = self._find_part_by_id(p["id"])
            
            versions = []
            for v in p["versions"]:
                if v in ("__COMPUTED_BASE__", "__SILENT__"):
                    versions.append(v)
                else:
                    full_path = os.path.join(parts_dir, v)
                    if os.path.exists(full_path):
                        versions.append(full_path)
            
            if p.get("has_base", False) and (not versions or versions[0] != "__COMPUTED_BASE__"):
                versions.insert(0, "__COMPUTED_BASE__")
            
            if not versions:
                if existing and existing in self.part_groups:
                    self.part_groups.remove(existing)
                continue
            
            if existing:
                existing.start = p["start"]
                existing.end = p["end"]
                existing.has_base = p.get("has_base", False)
                existing.last_blend = p.get("last_blend", 0)
                existing.last_preserve = p.get("last_preserve", True)
                existing.apply_order = p.get("apply_order", 0)
                existing.volume_db = p.get("volume_db", 0)
                existing.versions = versions
                existing.version_params = p.get("version_params", [None] * len(versions))
                while len(existing.version_params) < len(versions):
                    existing.version_params.append(None)
                existing.active_idx = min(p["active_idx"], max(0, len(versions) - 1))
            else:
                g = PartGroup(p["start"], p["end"], parts_dir, self.sr)
                g.id = p["id"]
                g.versions = versions
                g.version_params = p.get("version_params", [None] * len(versions))
                while len(g.version_params) < len(versions):
                    g.version_params.append(None)
                g.active_idx = min(p["active_idx"], max(0, len(versions) - 1))
                g.has_base = p.get("has_base", False)
                g.last_blend = p.get("last_blend", 0)
                g.last_preserve = p.get("last_preserve", True)
                g.apply_order = p.get("apply_order", 0)
                g.volume_db = p.get("volume_db", 0)
                self.part_groups.append(g)
        
        if self.part_groups:
            self._apply_counter = max(g.apply_order for g in self.part_groups)
        
        self._rebuild_result_from_parts()
        return True
    
    def _undo(self):
        if not self.history or not self.history.can_undo():
            self.log(tr("Nothing to undo"))
            return
        
        snapshot = self.history.undo()
        if snapshot and self._restore_snapshot(snapshot):
            self._redraw()
            self._save_project()
            self.log("↶ Undo")
    
    def _redo(self):
        if not self.history or not self.history.can_redo():
            self.log(tr("Nothing to redo"))
            return
        
        snapshot = self.history.redo()
        if snapshot and self._restore_snapshot(snapshot):
            self._redraw()
            self._save_project()
            self.log("↷ Redo")
    
    def _on_key_press(self, e):
        try:
            if self.parent.master.index(self.parent.master.select()) != 0:
                return
        except:
            pass
        
        kc = e.keycode
        ctrl = bool(e.state & 0x4)
        shift = bool(e.state & 0x1)
        
        if kc == 73 and not ctrl:
            self._hotkey_marker()
            return "break"
        if kc == 82 and not ctrl:
            self._convert()
            return "break"
        if kc == 32 and not ctrl:
            self._toggle_play()
            return "break"
        if kc == 76 and not ctrl:
            self._create_silent_part()
            return "break"
        if (kc == 187 or kc == 107) and not ctrl:
            self._adjust_volume(1)
            return "break"
        if (kc == 189 or kc == 109) and not ctrl:
            self._adjust_volume(-1)
            return "break"
        if kc == 37:
            if shift and not self._is_playing:
                self._extend_selection(-1)
            else:
                self._move_cursor(-self._get_cursor_step(large=False))
            return "break"
        if kc == 39:
            if shift and not self._is_playing:
                self._extend_selection(1)
            else:
                self._move_cursor(self._get_cursor_step(large=False))
            return "break"
        if kc == 90 and ctrl:
            (self._redo if shift else self._undo)()
            return "break"
        if kc == 89 and ctrl:
            self._redo()
            return "break"
        if kc == 46:
            self._hotkey_delete()
            return "break"
        if 48 <= kc <= 57:
            self._process_number_key(kc - 48)
            return "break"
        if 96 <= kc <= 105:
            self._process_number_key(kc - 96)
            return "break"

    def _to_mono(self, audio):
        if audio is None:
            return None
        return audio.mean(axis=1).astype(np.float32) if len(audio.shape) > 1 else audio.astype(np.float32)
    
    def _get_fade_curves(self, length):
        t = np.linspace(0, 1, length, dtype=np.float32)
        if self.crossfade_type == 0:
            return t, 1 - t
        else:
            return np.sin(t * np.pi / 2), np.cos(t * np.pi / 2)
    
    def _compute_base_for_part(self, part):
        start, end = part.start, part.end
        length = end - start
        base = np.zeros(length, dtype=np.float32)
        
        underlying = [g for g in self.part_groups 
                      if g.id != part.id 
                      and g.apply_order < part.apply_order
                      and g.start < end and g.end > start]
        
        if not underlying:
            return base
        
        underlying.sort(key=lambda g: g.apply_order)
        
        for g in underlying:
            data = self._get_part_data(g)
            if data is None:
                continue
            
            skip_vol = g.has_base and g.active_idx == 0 and len(g.versions) > 1
            if g.volume_db != 0 and not skip_vol:
                gain = 10 ** (g.volume_db / 20)
                data = data * gain
            
            overlap_start = max(g.start, start)
            overlap_end = min(g.end, end)
            if overlap_start >= overlap_end:
                continue
            
            base_pos = overlap_start - start
            data_pos = overlap_start - g.start
            copy_len = min(overlap_end - overlap_start, len(data) - data_pos, length - base_pos)
            
            if copy_len > 0:
                base[base_pos:base_pos + copy_len] = data[data_pos:data_pos + copy_len]
        
        return base
    
    def _get_part_data(self, part, idx=None):
        if idx is None:
            idx = part.active_idx
        
        if part.has_base and idx == 0:
            return self._compute_base_for_part(part)
        
        data = part.get_data(idx)
        if data is None:
            return None
        
        nan_mask = np.isnan(data)
        if np.any(nan_mask):
            base = self._compute_base_for_part(part)
            if base is not None and len(base) == len(data):
                data = data.copy()
                data[nan_mask] = base[nan_mask]
            else:
                data = np.nan_to_num(data, nan=0.0)
        
        return data
    
    def _set_blend(self, value):
        self.blend_mode = value
        self._update_blend_buttons()
        self.log(f"Blend: {value} {tr('ms')}")
    
    def _update_blend_buttons(self):
        for val, btn in self.blend_btns.items():
            btn.state(['pressed'] if val == self.blend_mode else ['!pressed'])
    
    def _toggle_crossfade_type(self):
        self.crossfade_type = (self.crossfade_type + 1) % 2
        self._update_crossfade_btn()
        name = tr("Linear blend") if self.crossfade_type == 0 else tr("Smooth blend")
        self.log(f"Crossfade: {name}")

    def _update_crossfade_btn(self):
        name = tr("Linear blend") if self.crossfade_type == 0 else tr("Smooth blend")
        self.crossfade_btn.config(text=name)
    
    def _write_audio(self, data, start, fade_ms=0):
        if data is None or len(data) == 0:
            return
        
        write_len = len(data)
        end = start + write_len
        
        if end > self.total_samples:
            end = self.total_samples
            write_len = end - start
            data = data[:write_len]
        
        if write_len <= 0:
            return
        
        if fade_ms == 0 or write_len < 200 or self.result_audio is None:
            self.result_audio[start:end] = data
            self.result_audio_display[start:end] = data
            return
        
        fade_samples = min(int(self.sr * fade_ms / 1000), write_len // 4)
        fade_samples = max(20, fade_samples)
        
        result = data.copy()
        fade_in, fade_out = self._get_fade_curves(fade_samples)
        
        old_left = self.result_audio[start:start + fade_samples].copy()
        if np.any(np.abs(old_left) > 0.0001):
            result[:fade_samples] = old_left * fade_out + result[:fade_samples] * fade_in
        
        old_right = self.result_audio[end - fade_samples:end].copy()
        if np.any(np.abs(old_right) > 0.0001):
            result[-fade_samples:] = result[-fade_samples:] * fade_out + old_right * fade_in
        
        self.result_audio[start:end] = result
        self.result_audio_display[start:end] = result
    
    def _toggle_source_mode(self):
        if not self.is_stereo:
            return
        modes = ["F", "L", "R"]
        idx = modes.index(self.source_mode) if self.source_mode in modes else 0
        self.source_mode = modes[(idx + 1) % 3]
        self.source_mode_btn.config(text=self.source_mode)
        names = {"F": "Full", "L": "Left", "R": "Right"}
        self.log(f"Source: {names[self.source_mode]}")
    
    def _get_source_for_convert(self, start, end):
        data = self.source_audio[start:end].copy()
        if not self.is_stereo or self.source_mode == "F":
            return data
        if self.source_mode == "L":
            return data[:, 0]
        return data[:, 1]
    
    def _get_project_dir(self):
        if not self.source_path:
            return None
        name = os.path.splitext(os.path.basename(self.source_path))[0]
        return os.path.join(self.get_output_dir(), "editor", name)
    
    def _get_parts_dir(self):
        project_dir = self._get_project_dir()
        d = os.path.join(project_dir, "parts") if project_dir else os.path.join(self.get_output_dir(), "editor", "_temp", "parts")
        os.makedirs(d, exist_ok=True)
        return d
    
    def _save_project(self):
        project_dir = self._get_project_dir()
        if not project_dir or self.source_audio is None:
            return
        
        os.makedirs(project_dir, exist_ok=True)
        import soundfile as sf
        
        if self.result_audio is not None:
            sf.write(os.path.join(project_dir, "result.wav"), self.result_audio, self.sr)
        
        data = {
            "markers": self.markers,
            "sel_start": self.sel_start,
            "sel_end": self.sel_end,
            "cursor_pos": self.cursor_pos,
            "zoom": self.zoom,
            "offset": self.offset,
            "active_track": self._active_track,
            "source_mode": self.source_mode,
            "parts": [g.to_dict() for g in self.part_groups]
        }
        
        with open(os.path.join(project_dir, "project.json"), 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def _load_project(self):
        project_dir = self._get_project_dir()
        if not project_dir:
            return False
        
        project_file = os.path.join(project_dir, "project.json")
        if not os.path.exists(project_file):
            return False
        
        try:
            import soundfile as sf
            
            with open(project_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            result_path = os.path.join(project_dir, "result.wav")
            if os.path.exists(result_path):
                result, _ = sf.read(result_path)
                self.result_audio = result.astype(np.float32)
                self.result_audio_display = self._to_mono(result)
            
            self.markers = data.get("markers", [])
            self.sel_start = data.get("sel_start")
            self.sel_end = data.get("sel_end")
            self.cursor_pos = data.get("cursor_pos", 0)
            self.zoom = data.get("zoom", 1.0)
            self.offset = data.get("offset", 0)
            self._active_track = data.get("active_track", "source")
            
            saved_mode = data.get("source_mode", "F")
            if self.is_stereo:
                self.source_mode = saved_mode if saved_mode in ("F", "L", "R") else "F"
            else:
                self.source_mode = "M"
            self.source_mode_btn.config(text=self.source_mode)
            
            parts_dir = self._get_parts_dir()
            for p in data.get("parts", []):
                versions = []
                for v in p["versions"]:
                    if v in ("__COMPUTED_BASE__", "__SILENT__"):
                        versions.append(v)
                    else:
                        full_path = os.path.join(parts_dir, v)
                        if os.path.exists(full_path):
                            versions.append(full_path)
                
                if p.get("has_base", False) and (not versions or versions[0] != "__COMPUTED_BASE__"):
                    versions.insert(0, "__COMPUTED_BASE__")
                
                if not versions:
                    continue
                
                g = PartGroup(p["start"], p["end"], parts_dir, self.sr)
                g.id = p["id"]
                g.versions = versions
                g.version_params = p.get("version_params", [None] * len(versions))
                while len(g.version_params) < len(versions):
                    g.version_params.append(None)
                g.active_idx = min(p["active_idx"], len(versions) - 1)
                g.has_base = p.get("has_base", False)
                g.last_blend = p.get("last_blend", 0)
                g.last_preserve = p.get("last_preserve", True)
                g.apply_order = p.get("apply_order", 0)
                g.volume_db = p.get("volume_db", 0)
                self.part_groups.append(g)
            
            if self.part_groups:
                self._apply_counter = max(g.apply_order for g in self.part_groups)
            
            self._compute_overwritten_ranges()
            self.log(tr("Project loaded"))
            return True
            
        except Exception as e:
            self.log(f"{tr('Project load error:')} {e}")
            return False
    
    def _assign_levels(self):
        if not self.part_groups:
            return
        sorted_groups = sorted(self.part_groups, key=lambda g: (g.start, -(g.end - g.start)))
        level_ends = []
        for g in sorted_groups:
            placed = False
            for level, end in enumerate(level_ends):
                if g.start >= end:
                    g.level = level
                    level_ends[level] = g.end
                    placed = True
                    break
            if not placed:
                g.level = len(level_ends)
                level_ends.append(g.end)
    
    def _merge_ranges(self, ranges):
        if not ranges:
            return []
        sorted_ranges = sorted(ranges)
        merged = [sorted_ranges[0]]
        for start, end in sorted_ranges[1:]:
            if start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        return merged

    def _compute_overwritten_ranges(self):
        for part in self.part_groups:
            part.overwritten_ranges = []
            for other in self.part_groups:
                if other.id == part.id:
                    continue
                if other.has_base and other.active_idx == 0:
                    continue
                
                overlap_start = max(part.start, other.start)
                overlap_end = min(part.end, other.end)
                if overlap_start >= overlap_end:
                    continue
                
                other_overwrites_part = False
                
                if other.apply_order > part.apply_order:
                    part_nested_in_other = (part.start >= other.start and part.end <= other.end)
                    if not part_nested_in_other or not other.last_preserve:
                        other_overwrites_part = True
                else:
                    other_nested_in_part = (other.start >= part.start and other.end <= part.end)
                    if other_nested_in_part and part.last_preserve:
                        other_overwrites_part = True
                
                if other_overwrites_part:
                    part.overwritten_ranges.append((overlap_start, overlap_end))
            
            if len(part.overwritten_ranges) > 1:
                part.overwritten_ranges = self._merge_ranges(part.overwritten_ranges)
    
    def on_tab_activated(self):
        saved = self.get_editor_file()
        if saved and os.path.exists(saved) and self.source_path != saved:
            self._load_file(saved)
        if self.sr and not self._stream_active:
            self._init_stream()
        self.update_preset_display()
    
    def on_tab_deactivated(self):
        self._is_playing = False
        self._stop_stream()
        self.play_btn.config(text="▶")
        self.play_pos = None
        self._save_project()
    
    def cleanup(self):
        self._save_project()
        self._stop_stream()
    
    def update_preset_display(self):
        p = self.get_preset_info()
        if not p.get("model"):
            self.preset_lbl.config(text=tr("(no model)"), foreground='#666')
            return
        m = os.path.splitext(p["model"])[0]
        m = m[:10] + ".." if len(m) > 12 else m
        F0_SHORT = {"rmvpe": "RM", "mangio-crepe": "MC", "mangio-crepe-tiny": "MCt",
                    "crepe": "CR", "crepe-tiny": "CRt", "harvest": "HV", "pm": "PM"}
        f0 = F0_SHORT.get(p.get("f0_method", ""), "?")
        def fmt(v): return f"{v:.2f}".lstrip('0') or '0'
        parts = [f0, f"{p.get('pitch', 0):+d}", f"I{fmt(p.get('index_rate', .9))}",
                 f"F{p.get('filter_radius', 3)}", f"M{fmt(p.get('rms_mix_rate', .25))}",
                 f"P{fmt(p.get('protect', .33))}"]
        if p.get('resample_sr'): parts.append(f"R{p['resample_sr'] // 1000}k")
        if "crepe" in p.get("f0_method", ""): parts.append(f"H{p.get('crepe_hop_length', 120)}")
        self.preset_lbl.config(text=f"{m} | {' '.join(parts)}", foreground='#aaa')
    
    def on_preset_loaded(self):
        self.update_preset_display()
        if self.source_audio is not None and not self._is_converting:
            self._convert()
        
    def _scan_devices(self):
        try:
            import sounddevice as sd
            self.output_devices = []
            for i, d in enumerate(sd.query_devices()):
                if d['max_output_channels'] > 0:
                    name = d['name'][:40]
                    if d['max_input_channels'] == 0 or not any(n == name for _, n in self.output_devices):
                        self.output_devices.append((i, name))
            self.device_combo['values'] = [n for _, n in self.output_devices]
            if not self.output_devices: return
            try:
                default = sd.query_devices(kind='output')
                for i, (dev_id, name) in enumerate(self.output_devices):
                    if default['name'].startswith(name[:20]):
                        self.device_combo.current(i)
                        self.output_device = dev_id
                        return
            except: pass
            self.device_combo.current(0)
            self.output_device = self.output_devices[0][0]
        except Exception as e:
            self.log(f"{tr('Device scan error:')} {e}")
    
    def _rescan_devices(self):
        import sounddevice as sd
        old_name = next((n for d, n in self.output_devices if d == self.output_device), "")
        try: sd._terminate(); sd._initialize()
        except: pass
        self._scan_devices()
        for i, (d, n) in enumerate(self.output_devices):
            if n == old_name:
                self.device_combo.current(i)
                self.output_device = d
                break
        if self._stream_active: self._restart_stream()
            
    def _on_device_change(self, event=None):
        idx = self.device_combo.current()
        if 0 <= idx < len(self.output_devices):
            self.output_device = self.output_devices[idx][0]
            if self._stream_active: self._restart_stream()
        
    def _build(self):
        ctrl = ttk.Frame(self.parent)
        ctrl.pack(fill=tk.X, pady=(0, 3))
        
        ttk.Button(ctrl, text="📂", width=3, command=self._load).pack(side=tk.LEFT)
        self.file_lbl = ttk.Label(ctrl, text=tr("(file not selected)"), foreground='gray', width=20)
        self.file_lbl.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(ctrl, text="💾", width=3, command=self._save_result).pack(side=tk.LEFT)
        ttk.Separator(ctrl, orient='vertical').pack(side=tk.LEFT, fill=tk.Y, padx=6)
        
        self.play_btn = ttk.Button(ctrl, text="▶", width=3, command=self._toggle_play)
        self.play_btn.pack(side=tk.LEFT)
        
        self.active_lbl = ttk.Label(ctrl, text=f"[{tr('Source')}]", foreground='#5dade2', 
                                     font=('Segoe UI', 9, 'bold'))
        self.active_lbl.pack(side=tk.LEFT, padx=5)
        ttk.Separator(ctrl, orient='vertical').pack(side=tk.LEFT, fill=tk.Y, padx=6)
        
        self.preset_lbl = ttk.Label(ctrl, text="", foreground='#888')
        self.preset_lbl.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(ctrl, text=tr("Run"), command=self._convert).pack(side=tk.RIGHT)
        ttk.Separator(ctrl, orient='vertical').pack(side=tk.RIGHT, fill=tk.Y, padx=6)
        
        self.device_combo = ttk.Combobox(ctrl, state="readonly", width=25)
        self.device_combo.pack(side=tk.RIGHT, padx=2)
        self.device_combo.bind("<<ComboboxSelected>>", self._on_device_change)
        ttk.Button(ctrl, text="🔄", width=2, command=self._rescan_devices).pack(side=tk.RIGHT)
        
        tracks = ttk.Frame(self.parent)
        tracks.pack(fill=tk.BOTH, expand=True)
        
        for is_result, lbl, clr in [(True, "R", '#e74c3c'), (False, "S", '#5dade2')]:
            row = ttk.Frame(tracks)
            row.pack(fill=tk.BOTH, expand=True)
            ttk.Label(row, text=lbl, foreground=clr, font=('Consolas', 8), width=2).pack(side=tk.LEFT)
            wf = WaveformCanvas(row, self, is_result=is_result, height=90)
            wf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            setattr(self, 'result_wf' if is_result else 'source_wf', wf)
        
        time_frame = ttk.Frame(self.parent)
        time_frame.pack(fill=tk.X, pady=(2, 0))
        
        self.source_mode_btn = ttk.Button(time_frame, text="F", width=2, command=self._toggle_source_mode)
        self.source_mode_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.time_lbl = ttk.Label(time_frame, text="00:00.000 / 00:00.000", font=('Consolas', 9))
        self.time_lbl.pack(side=tk.LEFT)

        ttk.Label(time_frame, text=tr("ms"), foreground='#888').pack(side=tk.RIGHT)
        self.blend_btns = {}
        for val in reversed(BLEND_VALUES):
            btn = ttk.Button(time_frame, text=str(val), width=3, command=lambda v=val: self._set_blend(v))
            btn.pack(side=tk.RIGHT, padx=1)
            self.blend_btns[val] = btn
        self.crossfade_btn = ttk.Button(time_frame, width=24, command=self._toggle_crossfade_type)
        self.crossfade_btn.pack(side=tk.RIGHT, padx=(10, 2))
        self._update_blend_buttons()
        self._update_crossfade_btn()
        
        self.sel_lbl = ttk.Label(time_frame, text="", foreground='gray', font=('Consolas', 9))
        self.sel_lbl.pack(side=tk.RIGHT)        
        
    def _s2x(self, sample, width):
        if self.total_samples == 0: return 0
        return int((sample - self.offset) / (self.total_samples / self.zoom) * width)
    
    def _x2s(self, x, width):
        if self.total_samples == 0: return 0
        return int(self.offset + x / width * self.total_samples / self.zoom)
    
    def _clamp_offset(self):
        visible = int(self.total_samples / self.zoom)
        self.offset = max(0, min(self.total_samples - visible, self.offset))
    
    def _on_zoom(self, e, width):
        if self.source_audio is None: return
        mouse_s = self._x2s(e.x, width)
        self.zoom = max(1.0, min(2000.0, self.zoom * (1.25 if e.delta > 0 else 0.8)))
        self.offset = int(mouse_s - (self.total_samples / self.zoom) * e.x / max(1, width))
        self._clamp_offset()
        self._redraw()
    
    def _on_scroll(self, e, width):
        if self.source_audio is None: return
        self.offset += int(self.total_samples / self.zoom * 0.05) * (-1 if e.delta > 0 else 1)
        self._clamp_offset()
        self._redraw()
        
    def _on_click(self, e, width, is_result):
        if self.source_audio is None: return
        self._active_track = 'result' if is_result else 'source'
        self._update_active_label()
        sample = max(0, min(self.total_samples - 1, self._x2s(e.x, width)))
        
        if e.state & 0x1:
            anchor = (min(self.sel_start, self.sel_end) if self.sel_start is not None 
                      else (self.cursor_pos or 0))
            if self.sel_start is not None:
                s1, s2 = sorted([self.sel_start, self.sel_end])
                anchor = s2 if abs(sample - s1) < abs(sample - s2) else s1
            self.sel_start, self.sel_end = (sample, anchor) if sample < anchor else (anchor, sample)
            self._drag_mode = 'left' if sample < anchor else 'right'
            self._redraw()
            self._update_time()
            return
        
        if self.sel_start is not None:
            s1, s2 = sorted([self.sel_start, self.sel_end])
            if abs(e.x - self._s2x(s1, width)) < 6:
                self._drag_mode = 'left'
                return
            if abs(e.x - self._s2x(s2, width)) < 6:
                self._drag_mode = 'right'
                return
        
        self._drag_mode = 'select'
        self.sel_start = self.sel_end = self.cursor_pos = sample
        self._redraw()
        self._update_time()
    
    def _on_double_click(self, e, width, is_result):
        if self.source_audio is None: return
        sample = self._x2s(e.x, width)
        
        if is_result:
            matching = [g for g in self.part_groups if g.start <= sample < g.end]
            if matching:
                smallest = min(matching, key=lambda g: g.size())
                self.sel_start, self.sel_end = smallest.start, smallest.end
                self._redraw()
                self._update_time()
                return
        else:
            sorted_markers = sorted([0] + self.markers + [self.total_samples])
            for i in range(len(sorted_markers) - 1):
                if sorted_markers[i] <= sample < sorted_markers[i + 1]:
                    self.sel_start = sorted_markers[i]
                    self.sel_end = sorted_markers[i + 1]
                    self._redraw()
                    self._update_time()
                    return
        
    def _on_drag(self, e, width):
        if self._drag_mode is None or self.source_audio is None: return
        sample = max(0, min(self.total_samples - 1, self._x2s(e.x, width)))
        if self._drag_mode == 'select':
            self.sel_end = sample
        elif self._drag_mode == 'left':
            self.sel_start, self.sel_end = sample, max(self.sel_start, self.sel_end)
        else:
            self.sel_start, self.sel_end = min(self.sel_start, self.sel_end), sample
        self._redraw()
        self._update_time()
        
    def _on_release(self, width=None):
        if width is None:
            width = self.source_wf.winfo_width()
        
        if self.sel_start is not None:
            if abs(self.sel_end - self.sel_start) < 100:
                self.cursor_pos = self._snap_to_points(self.sel_start, width)
                self.sel_start = self.sel_end = None
            else:
                s1, s2 = sorted([self.sel_start, self.sel_end])
                s1 = self._snap_to_points(s1, width)
                s2 = self._snap_to_points(s2, width)
                self.sel_start, self.sel_end = s1, s2
        
        self._drag_mode = None
        self._redraw()
        self._update_time()

    def _snap_to_points(self, sample, width, snap_to_markers=True, snap_to_selection=False, exclude_part=None):
        if self.total_samples == 0 or width <= 0:
            return sample
        
        samples_per_px = self.total_samples / self.zoom / width
        threshold = max(1, int(SNAP_THRESHOLD_PX * samples_per_px))
        
        snap_points = []
        for g in self.part_groups:
            if g is not exclude_part:
                snap_points.extend([g.start, g.end])
        
        if snap_to_markers:
            snap_points.extend(self.markers)
        
        if snap_to_selection and self.sel_start is not None:
            snap_points.extend([self.sel_start, self.sel_end])
        
        best, best_dist = sample, threshold + 1
        for pt in snap_points:
            dist = abs(sample - pt)
            if dist < best_dist:
                best, best_dist = pt, dist
        
        return best if best_dist <= threshold else sample
    
    def _get_cursor_step(self, large=False):
        if self.total_samples == 0 or self.sr is None:
            return 0
        
        if self._is_playing:
            return int(self.sr * (5.0 if large else 1.0))
        else:
            visible = int(self.total_samples / self.zoom)
            return max(1, visible // (20 if large else 200))
    
    def _move_cursor(self, delta):
        if self.source_audio is None:
            return
        
        if self._is_playing:
            new_pos = max(self._play_start, min(self._play_end - 1, self._play_pos + delta))
            self._play_pos = new_pos
            self.play_pos = new_pos
            self._update_playhead()
            self._update_time()
        else:
            pos = self.cursor_pos if self.cursor_pos is not None else 0
            pos = max(0, min(self.total_samples - 1, pos + delta))
            self.cursor_pos = pos
            self.sel_start = self.sel_end = None
            self._redraw()
            self._update_time()

    def _extend_selection(self, delta):
        if self.source_audio is None:
            return
        
        step = self._get_cursor_step(large=False)
        
        if self.sel_start is None:
            anchor = self.cursor_pos if self.cursor_pos is not None else 0
            new_pos = max(0, min(self.total_samples - 1, anchor + delta * step))
            self.sel_start, self.sel_end = min(anchor, new_pos), max(anchor, new_pos)
        else:
            s1, s2 = sorted([self.sel_start, self.sel_end])
            if delta < 0:
                s1 = max(0, s1 + delta * step)
            else:
                s2 = min(self.total_samples - 1, s2 + delta * step)
            self.sel_start, self.sel_end = s1, s2
        
        self._redraw()
        self._update_time()

    def _hotkey_delete(self, e=None):
        try:
            nb = self.parent.master
            if nb.index(nb.select()) != 0:
                return
        except:
            pass
        
        if self.source_audio is None or not self.part_groups:
            return "break"
        
        pos = self.cursor_pos or 0
        matching = [g for g in self.part_groups if g.start <= pos < g.end]
        if not matching:
            return "break"
        
        part = min(matching, key=lambda g: g.size())
        
        if part.has_base and part.active_idx == 0:
            return "break"
        
        if len(part.versions) <= 1:
            return "break"
        
        end = part.end
        idx = part.active_idx
        
        part.versions.pop(idx)
        part.version_params.pop(idx)
        part.active_idx = min(idx, len(part.versions) - 1)
        
        if part.has_base and len(part.versions) == 1:
            base_data = self._compute_base_for_part(part)
            if base_data is not None and len(base_data) > 0:
                exp_len = part.end - part.start
                if len(base_data) != exp_len:
                    tmp = np.zeros(exp_len, dtype=np.float32)
                    tmp[:min(len(base_data), exp_len)] = base_data[:exp_len]
                    base_data = tmp
                self.result_audio[part.start:part.end] = base_data
                self.result_audio_display[part.start:part.end] = base_data
            self.part_groups.remove(part)
            self._push_snapshot()
            self._save_project()
            self.log(tr("Part deleted, data restored"))
            self._redraw()
            self._play_after_action(pos, end)
            return "break"
        
        self._apply_version(part)
        self._push_snapshot()
        self._save_project()
        
        label = part.version_label(part.active_idx)
        params_str = part.format_params(part.active_idx)
        self.log(f"{tr('Version deleted')} → {label}: {params_str}" if params_str else f"{tr('Version deleted')} → {label}")
        self._redraw()
        self._play_after_action(pos, end)
        
        return "break"
    
    def _play_after_action(self, pos, end):
        self._active_track = 'result'
        self._update_active_label()
        if not self._stream_active:
            self._init_stream()
        self._play_pos = self._play_start = pos
        self._play_end = end
        self._is_playing = True
        self.play_btn.config(text="⏸")

    def _calc_play_end(self, pos):
        if self.sel_start is not None:
            s1, s2 = sorted([self.sel_start, self.sel_end])
            if s1 <= pos < s2:
                return s2
        return self.total_samples

    def _find_group(self, start, end):
        for g in self.part_groups:
            if g.start == start and g.end == end:
                return g
        return None
    
    def _get_group_at(self, sample):
        matching = [g for g in self.part_groups if g.start <= sample < g.end]
        return max(matching, key=lambda g: g.level) if matching else None
    
    def _switch_version_at(self, sample, delta):
        g = self._get_group_at(sample)
        if g:
            self._switch_version_and_play(g, delta)
    
    def _switch_version_and_play(self, part, delta):
        if len(part.versions) <= 1:
            return
        new_idx = (part.active_idx + delta) % len(part.versions)
        if new_idx == part.active_idx:
            return
        
        proceed, preserve_nested = self._ask_nested_action(part)
        if not proceed:
            return
        
        part.active_idx = new_idx
        self._apply_version(part, preserve_nested)
        self._push_snapshot()
        self._save_project()
        
        label = part.version_label(part.active_idx)
        params_str = part.format_params(part.active_idx)
        self.log(f"{label}: {params_str}" if params_str else label)
        
        self._active_track = 'result'
        self._update_active_label()
        
        if not self._stream_active:
            self._init_stream()
        
        pos = self.cursor_pos or 0
        if not (part.start <= pos < part.end):
            pos = part.start
        
        self._play_pos = self._play_start = pos
        self._play_end = self._calc_play_end(pos)
        self._is_playing = True
        self.play_btn.config(text="⏸")
    
    def _apply_version_data(self, group, preserve_nested=False, blend_override=None):
        data = self._get_part_data(group)
        if data is None:
            return
        
        skip_vol = group.has_base and group.active_idx == 0 and len(group.versions) > 1
        if group.volume_db != 0 and not skip_vol:
            gain = 10 ** (group.volume_db / 20)
            data = data * gain
        
        blend = blend_override if blend_override is not None else self.blend_mode
        max_len = group.end - group.start
        write_len = min(len(data), max_len)
        if write_len <= 0:
            return
        
        write_data = data[:write_len]
        write_end = group.start + write_len
        is_base = group.has_base and group.active_idx == 0
        
        need_fade = blend > 0 and (not is_base or (group.volume_db != 0 and not skip_vol))
        need_tail = write_len < max_len and not is_base
        
        base_data = None
        if need_fade or need_tail:
            base_data = self._compute_base_for_part(group)
        
        use_fade = 0
        if need_fade and base_data is not None and np.any(np.abs(base_data) > 0.0001):
            use_fade = blend
        
        if preserve_nested:
            nested = self._get_nested_parts(group)
            if nested:
                occupied = sorted([(n.start - group.start, n.end - group.start) for n in nested])
                segments = []
                current = 0
                
                for occ_start, occ_end in occupied:
                    seg_end = min(occ_start, write_len)
                    if current < seg_end:
                        segments.append((group.start + current, group.start + seg_end, current, seg_end))
                    current = max(current, occ_end)
                
                if current < write_len:
                    segments.append((group.start + current, write_end, current, write_len))
                
                for i, (abs_s, abs_e, d_s, d_e) in enumerate(segments):
                    seg_data = write_data[d_s:d_e]
                    
                    if use_fade > 0 and base_data is not None:
                        base_seg = base_data[d_s:d_e] if d_e <= len(base_data) else base_data[d_s:]
                        seg_len = min(len(base_seg), abs_e - abs_s)
                        if seg_len > 0:
                            self.result_audio[abs_s:abs_s + seg_len] = base_seg[:seg_len]
                            self.result_audio_display[abs_s:abs_s + seg_len] = base_seg[:seg_len]
                        
                        is_first = (i == 0)
                        is_last = (i == len(segments) - 1)
                        if is_first or is_last:
                            self._write_audio_segment(seg_data, abs_s, 
                                                     fade_left=is_first, fade_right=is_last,
                                                     fade_ms=use_fade)
                        else:
                            self.result_audio[abs_s:abs_e] = seg_data
                            self.result_audio_display[abs_s:abs_e] = seg_data
                    else:
                        self.result_audio[abs_s:abs_e] = seg_data
                        self.result_audio_display[abs_s:abs_e] = seg_data
            else:
                if use_fade > 0 and base_data is not None:
                    base_len = min(len(base_data), max_len)
                    self.result_audio[group.start:group.start + base_len] = base_data[:base_len]
                    self.result_audio_display[group.start:group.start + base_len] = base_data[:base_len]
                self._write_audio(write_data, group.start, fade_ms=use_fade)
        else:
            if use_fade > 0 and base_data is not None:
                base_len = min(len(base_data), max_len)
                self.result_audio[group.start:group.start + base_len] = base_data[:base_len]
                self.result_audio_display[group.start:group.start + base_len] = base_data[:base_len]
            self._write_audio(write_data, group.start, fade_ms=use_fade)
        
        if need_tail and base_data is not None:
            tail_start = write_len
            tail_end = min(len(base_data), max_len)
            if tail_end > tail_start:
                tail_data = base_data[tail_start:tail_end]
                if np.any(np.abs(tail_data) > 0.0001):
                    abs_start = group.start + tail_start
                    self.result_audio[abs_start:abs_start + len(tail_data)] = tail_data
                    self.result_audio_display[abs_start:abs_start + len(tail_data)] = tail_data
                    
    def _apply_version(self, group, preserve_nested=False, blend_override=None, update_state=True):
        blend = blend_override if blend_override is not None else self.blend_mode
        
        if update_state:
            group.last_blend = blend
            group.last_preserve = preserve_nested
            self._apply_counter += 1
            group.apply_order = self._apply_counter
        
        self._apply_version_data(group, preserve_nested, blend)
        self._compute_overwritten_ranges()
        self._redraw_result()
    
    def _write_audio_segment(self, data, start, fade_left=True, fade_right=True, fade_ms=None):
        if fade_ms is None:
            fade_ms = self.blend_mode
            
        if data is None or len(data) == 0:
            return
        
        write_len = len(data)
        end = start + write_len
        
        if write_len < 100 or self.result_audio is None or fade_ms == 0:
            self.result_audio[start:end] = data
            self.result_audio_display[start:end] = data
            return
        
        fade_samples = min(int(self.sr * fade_ms / 1000), write_len // 4)
        fade_samples = max(20, fade_samples)
        
        result = data.copy()
        fade_in, fade_out = self._get_fade_curves(fade_samples)
        
        if fade_left:
            old_left = self.result_audio[start:start + fade_samples].copy()
            if np.any(np.abs(old_left) > 0.0001):
                result[:fade_samples] = old_left * fade_out + result[:fade_samples] * fade_in
        
        if fade_right:
            old_right = self.result_audio[end - fade_samples:end].copy()
            if np.any(np.abs(old_right) > 0.0001):
                result[-fade_samples:] = result[-fade_samples:] * fade_out + old_right * fade_in
        
        self.result_audio[start:end] = result
        self.result_audio_display[start:end] = result

    def _get_nested_parts(self, part):
        return [g for g in self.part_groups 
                if g.id != part.id and g.start >= part.start and g.end <= part.end]

    def _is_replace_all_mode(self):
        try:
            import ctypes
            return ctypes.windll.user32.GetKeyState(0x14) & 1
        except:
            return False

    def _ask_nested_action(self, part):
        nested = self._get_nested_parts(part)
        if not nested:
            return (True, False)
        preserve_nested = not self._is_replace_all_mode()
        return (True, preserve_nested)

    def _show_part_menu(self, e, part):
        menu = tk.Menu(self.parent, tearoff=0)
        
        dur = (part.end - part.start) / self.sr
        menu.add_command(label=f"{part.start/self.sr:.1f}s - {part.end/self.sr:.1f}s ({dur:.2f}s)", state='disabled')
        menu.add_separator()
        
        for i in range(len(part.versions)):
            lbl = part.version_label(i)
            params_str = part.format_params(i)
            if params_str:
                lbl = f"{lbl}: {params_str}"
            prefix = "● " if i == part.active_idx else "  "
            menu.add_command(label=f"{prefix}{lbl}", command=lambda idx=i, p=part: self._set_version(p, idx))
        
        if len(part.versions) > 1:
            menu.add_separator()
            if not (part.has_base and part.active_idx == 0):
                menu.add_command(label=tr("Delete current version"), command=lambda: self._delete_version(part))
            menu.add_command(label=tr("Keep only current"), command=lambda: self._delete_others(part))
        
        menu.add_separator()
        menu.add_command(label=tr("Delete part (restore)"), command=lambda: self._delete_part(part))
        
        if len(self.part_groups) > 1:
            menu.add_separator()
            menu.add_command(label=tr("Flatten to single file"), command=self._flatten_parts)
        
        menu.tk_popup(e.x_root, e.y_root)
    
    def _set_version(self, part, idx):
        if idx < 0 or idx >= len(part.versions):
            return
        
        proceed, preserve_nested = self._ask_nested_action(part)
        if not proceed:
            return
        
        part.active_idx = idx
        self._apply_version(part, preserve_nested)
        self._push_snapshot()
        self._save_project()
        
        label = part.version_label(idx)
        params_str = part.format_params(idx)
        self.log(f"{label}: {params_str}" if params_str else label)
    
    def _delete_version(self, part):
        if len(part.versions) <= 1:
            return
        if part.has_base and part.active_idx == 0:
            return
        
        idx = part.active_idx
        part.versions.pop(idx)
        part.version_params.pop(idx)
        part.active_idx = min(idx, len(part.versions) - 1)
        
        self._apply_version(part)
        self._push_snapshot()
        self._save_project()
        
        self.log(f"{tr('Version deleted')} → {part.version_label(part.active_idx)}")
        self._redraw()
    
    def _delete_others(self, part):
        if len(part.versions) <= 1:
            return
        
        kept_path = part.versions[part.active_idx]
        kept_params = part.version_params[part.active_idx] if part.active_idx < len(part.version_params) else None
        
        real_count = len(part.versions) - 1 if part.has_base else len(part.versions)
        
        if part.has_base and real_count > 1 and part.active_idx > 0:
            base_path = part.versions[0]
            base_params = part.version_params[0] if part.version_params else None
            part.versions = [base_path, kept_path]
            part.version_params = [base_params, kept_params]
            part.active_idx = 1
        else:
            part.versions = [kept_path]
            part.version_params = [kept_params]
            part.active_idx = 0
            part.has_base = False
        
        self._push_snapshot()
        self._save_project()
        
        self.log(tr("Other versions deleted"))
        self._redraw()
    
    def _delete_part(self, part):
        if part.has_base:
            base_data = self._compute_base_for_part(part)
            if base_data is not None and len(base_data) > 0:
                exp_len = part.end - part.start
                if len(base_data) != exp_len:
                    tmp = np.zeros(exp_len, dtype=np.float32)
                    tmp[:min(len(base_data), exp_len)] = base_data[:exp_len]
                    base_data = tmp
                self.result_audio[part.start:part.end] = base_data
                self.result_audio_display[part.start:part.end] = base_data
        
        if part in self.part_groups:
            self.part_groups.remove(part)
        
        self._compute_overwritten_ranges()
        self._push_snapshot()
        self._save_project()
        
        self.log(tr("Part deleted, data restored"))
        self._redraw()
    
    def _delete_part_files(self, part):
        part.cleanup()
        self.part_groups.remove(part)
        self._push_snapshot()
        self._save_project()
        self.log(tr("Part files deleted"))
        self._redraw()
    
    def _flatten_parts(self):
        if not self.part_groups:
            return
        
        self.part_groups.clear()
        self._push_snapshot()
        self._save_project()
        
        self.log(tr("Parts flattened"))
        self._redraw()
    
    def _hotkey_marker(self, e=None):
        if self.source_audio is None:
            return "break"
        
        if self.sel_start is not None and abs(self.sel_end - self.sel_start) > 100:
            s1, s2 = sorted([self.sel_start, self.sel_end])
            added = 0
            if s1 not in self.markers and s1 > 0:
                self.markers.append(s1)
                added += 1
            if s2 not in self.markers and s2 < self.total_samples:
                self.markers.append(s2)
                added += 1
            if added:
                self.markers.sort()
                self._push_snapshot()
                self._save_project()
                self.log(f"{tr('Markers:')} {s1/self.sr:.2f}s, {s2/self.sr:.2f}s")
                self._redraw()
            return "break"
        
        if self.cursor_pos is not None:
            self._add_marker(self.cursor_pos)
        return "break"
    
    def _add_marker(self, sample):
        if sample in self.markers:
            return
        
        self.markers.append(sample)
        self.markers.sort()
        self._push_snapshot()
        self._save_project()
        
        self.log(f"{tr('Marker:')} {sample/self.sr:.2f}s")
        self._redraw()
    
    def _show_marker_menu(self, e, marker_idx):
        marker = self.markers[marker_idx]
        menu = tk.Menu(self.parent, tearoff=0)
        menu.add_command(label=f"{tr('Marker:')} {marker/self.sr:.2f}s", state='disabled')
        menu.add_separator()
        menu.add_command(label=tr("Delete"), command=lambda: self._remove_marker(marker_idx))
        if len(self.markers) > 1:
            menu.add_command(label=tr("Delete all markers"), command=self._clear_markers)
        menu.tk_popup(e.x_root, e.y_root)
    
    def _remove_marker(self, idx):
        if not (0 <= idx < len(self.markers)):
            return
        
        sample = self.markers.pop(idx)
        self._push_snapshot()
        self._save_project()
        
        self.log(f"{tr('Marker deleted:')} {sample/self.sr:.2f}s")
        self._redraw()
    
    def _clear_markers(self):
        if not self.markers:
            return
        
        self.markers.clear()
        self._push_snapshot()
        self._save_project()
        
        self.log(tr("All markers deleted"))
        self._redraw()
    
    def _switch_track_and_play(self, to_result, x, width):
        if (to_result and self._active_track != 'result') or (not to_result and self._active_track != 'source'):
            self._active_track = 'result' if to_result else 'source'
            self._update_active_label()
        if self.source_audio_display is None: return
        sample = max(0, min(self.total_samples - 1, self._x2s(x, width)))
        if not self._stream_active: self._init_stream()
        self._play_pos = self._play_start = sample
        self._play_end = self.total_samples
        self._is_playing = True
        self.play_btn.config(text="⏸")
        
    def _update_active_label(self):
        is_result = self._active_track == 'result'
        self.active_lbl.config(text=f"[{tr('Result')}]" if is_result else f"[{tr('Source')}]", 
                               foreground='#e74c3c' if is_result else '#5dade2')
            
    def _redraw(self):
        self.source_wf.draw()
        self.result_wf._wf_cache_key = None
        self.result_wf.draw()
        if self.play_pos is not None or self.source_wf._last_playhead_x is not None:
            self.source_wf.update_playhead()
            self.result_wf.update_playhead()
        
    def _redraw_result(self):
        self.result_wf._wf_cache_key = None
        self.result_wf.draw()
        if self.play_pos is not None or self.result_wf._last_playhead_x is not None:
            self.result_wf.update_playhead()
        
    def _update_playhead(self):
        self.source_wf.update_playhead()
        self.result_wf.update_playhead()
        
    def _update_time(self):
        if not self.sr:
            return
        def fmt(s): 
            sec = s / self.sr
            return f"{int(sec // 60):02d}:{sec % 60:06.3f}"
        
        current_pos = self._play_pos if self._is_playing else (self.cursor_pos or 0)
        self.time_lbl.config(text=f"{fmt(current_pos)} / {fmt(self.total_samples)}")
        
        if self.sel_start is not None:
            s1, s2 = sorted([self.sel_start, self.sel_end])
            self.sel_lbl.config(text=f"{tr('Selected:')} {(s2-s1)/self.sr:.2f}s")
        else:
            self.sel_lbl.config(text="")
            
    def _load(self):
        path = filedialog.askopenfilename(filetypes=[("WAV", "*.wav")])
        if path: self._load_file(path)
    
    def _load_file(self, path):
        if not os.path.exists(path):
            self.log(f"{tr('File not found:')} {path}")
            return False
        try:
            import soundfile as sf
            data, sr = sf.read(path)
            
            self.part_groups = []
            self.markers.clear()
            self.result_audio = None
            self.result_audio_display = None
            
            self.source_audio = data.astype(np.float32)
            self.is_stereo = len(data.shape) > 1
            self.source_audio_display = self._to_mono(data)
            
            self.source_mode = "M" if not self.is_stereo else "F"
            self.source_mode_btn.config(text=self.source_mode)
            
            self.source_path = path
            self.sr = sr
            self.total_samples = len(self.source_audio_display)
            self.zoom, self.offset = 1.0, 0
            self.sel_start = self.sel_end = None
            self.cursor_pos = 0
            self._active_track = 'source'
            
            self._load_project()
            self._init_history()
            self._init_stream()
            self._redraw()
            self._update_active_label()
            self._update_time()
            self.update_preset_display()
            
            stereo = " [stereo]" if self.is_stereo else ""
            name = os.path.basename(path)
            self.file_lbl.config(text=name[:18] + ('...' if len(name) > 18 else '') + stereo, foreground='')
            self.log(f"{tr('Loaded:')} {name} ({len(data)/sr:.1f}s, {sr}Hz{stereo})")
            
            self.set_editor_file(path)
            return True
        except Exception as e:
            self.log(f"{tr('Load error:')} {e}")
            return False
            
    def _save_result(self):
        if self.result_audio is None:
            self.log(tr("No result"))
            return
        project_dir = self._get_project_dir() or self.get_output_dir()
        
        preset = self.get_preset_info()
        model_name = os.path.splitext(preset["model"])[0] if preset.get("model") else ""
        source_name = os.path.splitext(os.path.basename(self.source_path))[0] if self.source_path else ""
        
        if model_name and source_name:
            default_name = f"{model_name} {source_name}.wav"
        elif source_name:
            default_name = f"{source_name}_converted.wav"
        else:
            default_name = "converted.wav"
        
        path = filedialog.asksaveasfilename(
            defaultextension=".wav", filetypes=[("WAV", "*.wav")],
            initialdir=project_dir, initialfile=default_name
        )
        if path:
            try:
                import soundfile as sf
                sf.write(path, self.result_audio, self.sr)
                self.log(f"{tr('Saved:')} {os.path.basename(path)}")
            except Exception as e:
                self.log(f"{tr('Error:')} {e}")
    
    def _get_active_audio(self):
        if self._active_track == 'result' and self.result_audio_display is not None:
            return self.result_audio_display
        return self.source_audio_display
    
    def _init_stream(self):
        self._stop_stream()
        if self.sr is None:
            return
        try:
            import sounddevice as sd
            
            def callback(outdata, frames, time_info, status):
                if not self._is_playing:
                    outdata.fill(0)
                    return
                audio = self._get_active_audio()
                if audio is None or self._play_pos >= self._play_end:
                    outdata.fill(0)
                    self._is_playing = False
                    self._play_pos = self._play_start
                    return
                chunk = min(frames, self._play_end - self._play_pos)
                outdata[:chunk, 0] = audio[self._play_pos:self._play_pos + chunk]
                outdata[chunk:] = 0
                self._play_pos += chunk
                self.play_pos = self._play_pos
            
            self._stream = sd.OutputStream(
                samplerate=self.sr, channels=1, callback=callback,
                device=self.output_device, blocksize=512, latency='low'
            )
            self._stream.start()
            self._stream_active = True
            
            def updater():
                while self._stream_active:
                    if self._is_playing:
                        self.parent.after_idle(self._update_playhead)
                        self.parent.after_idle(self._update_time)
                        self.parent.after_idle(self._sync_play_button)
                    interval = 0.05 / max(1, self.zoom ** 0.5)
                    interval = max(0.012, min(0.05, interval))
                    time.sleep(interval)
            threading.Thread(target=updater, daemon=True).start()
        except Exception as e:
            self.log(f"{tr('Audio error:')} {e}")
    
    def _stop_stream(self):
        self._is_playing = False
        self._stream_active = False
        if self._stream:
            try: self._stream.stop(); self._stream.close()
            except: pass
            self._stream = None
    
    def _restart_stream(self):
        was, pos = self._is_playing, self._play_pos
        self._init_stream()
        if was: self._play_pos = pos; self._is_playing = True
    
    def _sync_play_button(self):
        if self._is_playing:
            self.play_btn.config(text="⏸")
        else:
            self.play_btn.config(text="▶")
            self.play_pos = None
            self._redraw()
    
    def _toggle_play(self):
        if self.source_audio_display is None: return
        if not self._stream_active: self._init_stream()
        if self._is_playing:
            self._is_playing = False
            self.play_btn.config(text="▶")
            self.play_pos = None
            self._redraw()
        else:
            if self.sel_start is not None:
                start, end = sorted([self.sel_start, self.sel_end])
            else:
                start, end = self.cursor_pos or 0, self.total_samples
            if start < end:
                self._play_pos = self._play_start = start
                self._play_end = end
                self._is_playing = True
                self.play_btn.config(text="⏸")
        
    def _process_number_key(self, num):
        if self.source_audio is None or not self.part_groups:
            return
        
        pos = self.cursor_pos or 0
        matching = [g for g in self.part_groups if g.start <= pos < g.end]
        if not matching:
            return
        
        part = min(matching, key=lambda g: g.size())
        
        if num == 0:
            if not part.has_base:
                return
            target_idx = 0
        else:
            target_idx = num if part.has_base else num - 1
            if not (0 <= target_idx < len(part.versions)):
                return
        
        proceed, preserve_nested = self._ask_nested_action(part)
        if not proceed:
            return
        
        part.active_idx = target_idx
        self._apply_version(part, preserve_nested)
        self._push_snapshot()
        self._save_project()
        
        self._active_track = 'result'
        self._update_active_label()
        
        label = part.version_label(part.active_idx)
        params_str = part.format_params(part.active_idx)
        self.log(f"{label}: {params_str}" if params_str else label)
        
        if not self._stream_active:
            self._init_stream()
        
        self._play_pos = self._play_start = pos
        self._play_end = self._calc_play_end(pos)
        self._is_playing = True
        self.play_btn.config(text="⏸")
            
    def _create_silent_part(self):
        if self.source_audio is None:
            self.log(tr("Load file first"))
            return
        
        has_sel = self.sel_start is not None and abs(self.sel_end - self.sel_start) > 100
        if not has_sel:
            self.log(tr("Select a region first"))
            return
        
        start, end = sorted([self.sel_start, self.sel_end])
        first_convert = self.result_audio is None
        
        if self.result_audio is None or len(self.result_audio) != self.total_samples:
            self.result_audio = np.zeros(self.total_samples, dtype=np.float32)
            self.result_audio_display = np.zeros(self.total_samples, dtype=np.float32)
        
        existing_group = self._find_group(start, end)
        preserve_nested = not self._is_replace_all_mode()
        
        if existing_group is None:
            group = PartGroup(start, end, self._get_parts_dir(), self.sr)
            self.part_groups.append(group)
            if not first_convert and np.any(self.result_audio[start:end] != 0):
                group.set_base()
        else:
            group = existing_group
        
        group.add_silent_version()
        self._apply_version(group, preserve_nested, self.blend_mode)
        self._push_snapshot()
        self._save_project()
        
        self._active_track = 'result'
        self._update_active_label()
        self.log(f"✓ {tr('Silent part created')}")
        self._redraw()
    
    def _adjust_volume(self, delta):
        if self.source_audio is None or not self.part_groups:
            return
        
        pos = self.cursor_pos or 0
        matching = [g for g in self.part_groups if g.start <= pos < g.end]
        if not matching:
            return
        
        part = min(matching, key=lambda g: g.size())
        has_sel = self.sel_start is not None and abs(self.sel_end - self.sel_start) > 100
        
        if has_sel:
            s1, s2 = sorted([self.sel_start, self.sel_end])
            selection_inside = s1 >= part.start and s2 <= part.end and not (s1 == part.start and s2 == part.end)
        else:
            selection_inside = False
        
        apply_to_nested = self._is_replace_all_mode()
        
        if selection_inside:
            if self.result_audio is None or len(self.result_audio) != self.total_samples:
                self.result_audio = np.zeros(self.total_samples, dtype=np.float32)
                self.result_audio_display = np.zeros(self.total_samples, dtype=np.float32)
            
            new_part = PartGroup(s1, s2, self._get_parts_dir(), self.sr)
            new_part.set_base()
            new_part.volume_db = delta
            self._apply_counter += 1
            new_part.apply_order = self._apply_counter
            new_part.last_blend = self.blend_mode
            new_part.last_preserve = False
            self.part_groups.append(new_part)
            
            self._rebuild_result_from_parts()
            self._push_snapshot()
            self._save_project()
            self.log(f"{tr('Volume part:')} {new_part.volume_db:+d} dB")
        else:
            nested = self._get_nested_parts(part) if apply_to_nested else []
            
            part.volume_db += delta
            for n in nested:
                n.volume_db += delta
            
            self._rebuild_result_from_parts()
            self._push_snapshot()
            self._save_project()
            
            if nested:
                self.log(f"{tr('Volume:')} {part.volume_db:+d} dB (+{len(nested)})")
            else:
                self.log(f"{tr('Volume:')} {part.volume_db:+d} dB")
        
        self._redraw()
            
    def _convert(self):
        if self.source_audio is None:
            self.log(tr("Load file first"))
            return
        
        if self._is_converting:
            self.log(tr("Conversion in progress"))
            return
        
        has_sel = self.sel_start is not None and abs(self.sel_end - self.sel_start) > 100
        
        if not has_sel and self.result_audio is not None:
            if not messagebox.askyesno(tr("Confirm"), tr("No selection. Convert entire file?")):
                return
            
        def work():
            self._is_converting = True
            try:
                conv, params = self.get_converter()
                if not conv:
                    self.parent.after(0, lambda: self.log(tr("Converter not ready")))
                    return
                
                start, end = sorted([self.sel_start, self.sel_end]) if has_sel else (0, self.total_samples)
                if end - start < 1000:
                    self.parent.after(0, lambda: self.log(tr("Fragment too short")))
                    return
                
                padding_samples = int(self.sr * CONVERT_PADDING_MS / 1000)
                send_end = min(end + padding_samples, self.total_samples)
                
                import soundfile as sf
                project_dir = self._get_project_dir()
                tmp_dir = project_dir if project_dir else self.get_output_dir()
                if project_dir:
                    os.makedirs(project_dir, exist_ok=True)
                
                tmp_in = os.path.join(tmp_dir, "_temp_in.wav")
                tmp_out = os.path.join(tmp_dir, "_temp_out.wav")
                sf.write(tmp_in, self._get_source_for_convert(start, send_end), self.sr)
                
                self.parent.after(0, lambda: self.log(f"{tr('Converting')} {(end-start)/self.sr:.2f}s..."))
                self.set_progress(30, tr("Conversion..."))
                
                if conv.convert(tmp_in, tmp_out, **params) and os.path.exists(tmp_out):
                    converted, csr = sf.read(tmp_out)
                    converted = converted.astype(np.float32)
                    
                    if csr != self.sr:
                        import librosa
                        converted = librosa.resample(converted, orig_sr=csr, target_sr=self.sr)
                    
                    if len(converted.shape) > 1:
                        converted = converted.mean(axis=1).astype(np.float32)
                    
                    exp_len = end - start
                    write_len = min(len(converted), exp_len)
                    write_data = converted[:write_len]
                    
                    first_convert = self.result_audio is None
                    
                    if self.result_audio is None or len(self.result_audio) != self.total_samples:
                        self.result_audio = np.zeros(self.total_samples, dtype=np.float32)
                        self.result_audio_display = np.zeros(self.total_samples, dtype=np.float32)
                    
                    existing_group = self._find_group(start, end)
                    preserve_nested = not self._is_replace_all_mode()
                    
                    if existing_group is None:
                        group = PartGroup(start, end, self._get_parts_dir(), self.sr)
                        self.part_groups.append(group)
                        
                        if not first_convert:
                            existing = self.result_audio[start:end]
                            if np.any(existing != 0):
                                group.set_base()
                    else:
                        group = existing_group
                    
                    version_params = {
                        "pitch": params.get("pitch", 0),
                        "f0_method": params.get("f0_method", "rmvpe"),
                        "index_rate": params.get("index_rate", 0.9),
                        "filter_radius": params.get("filter_radius", 3),
                        "resample_sr": params.get("resample_sr", 0),
                        "rms_mix_rate": params.get("rms_mix_rate", 0.25),
                        "protect": params.get("protect", 0.33),
                        "crepe_hop_length": params.get("crepe_hop_length", 120),
                        "source_mode": self.source_mode
                    }
                    group.add_version(write_data, version_params)
                    
                    self._apply_version(group, preserve_nested, self.blend_mode)
                    self._push_snapshot()
                    
                    self._active_track = 'result'
                    self.parent.after(0, self._update_active_label)
                    self._save_project()
                    
                    ver_info = f" ({group.version_label(group.active_idx)})" if group.version_count() > 1 or group.has_base else ""
                    self.set_progress(100, f"✓ {tr('Done')}")
                    self.parent.after(0, lambda: self.log(f"✓ {tr('Done')}{ver_info}"))
                else:
                    self.set_progress(0, tr("Error"))
                    self.parent.after(0, lambda: self.log(tr("Conversion error")))
                    
                for f in [tmp_in, tmp_out]:
                    try: os.remove(f)
                    except: pass
                        
            except Exception as ex:
                import traceback
                traceback.print_exc()
                self.parent.after(0, lambda: self.log(f"{tr('Error:')} {ex}"))
                self.set_progress(0, tr("Error"))
            finally:
                self._is_converting = False
                
        threading.Thread(target=work, daemon=True).start()