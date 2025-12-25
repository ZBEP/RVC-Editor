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

SNAP_THRESHOLD_PX = 10

class EditorTab:
    
    def __init__(self, parent, get_converter_fn, log_fn, set_progress_fn, 
                 get_output_dir_fn, get_editor_file_fn, set_editor_file_fn,
                 get_preset_info_fn=None):
        self.parent = parent
        self.get_converter = get_converter_fn
        self.log = log_fn
        self.set_progress = set_progress_fn
        self.get_output_dir = get_output_dir_fn
        self.get_editor_file = get_editor_file_fn
        self.set_editor_file = set_editor_file_fn
        self.get_preset_info = get_preset_info_fn or (lambda: {})
        
        self.source_path = None
        self.source_audio = None
        self.result_audio = None
        self.source_audio_display = None
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
        self.source_mode = "F"
        self.output_device = None
        self.output_devices = []
        
        self._build()
        self._scan_devices()
        
        parent.winfo_toplevel().bind('<r>', self._hotkey_convert)
        parent.winfo_toplevel().bind('<space>', self._hotkey_play)
        parent.winfo_toplevel().bind('<i>', self._hotkey_marker)
        parent.winfo_toplevel().bind('<I>', self._hotkey_marker)
        parent.winfo_toplevel().bind('<Left>', self._hotkey_left)
        parent.winfo_toplevel().bind('<Right>', self._hotkey_right)
        parent.winfo_toplevel().bind('<Shift-Left>', self._hotkey_shift_left)
        parent.winfo_toplevel().bind('<Shift-Right>', self._hotkey_shift_right)
        
        for i in range(10):
            parent.winfo_toplevel().bind(f'<Key-{i}>', self._hotkey_number)
    
    def _to_mono(self, audio):
        if audio is None:
            return None
        return audio.mean(axis=1).astype(np.float32) if len(audio.shape) > 1 else audio.astype(np.float32)
    
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
        return data[:, 1]  # R
    
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
                versions = [os.path.join(parts_dir, v) for v in p["versions"] 
                           if os.path.exists(os.path.join(parts_dir, v))]
                if not versions:
                    continue
                g = PartGroup(p["start"], p["end"], parts_dir, self.sr)
                g.id = p["id"]
                g.active_idx = min(p["active_idx"], len(versions) - 1)
                g.has_base = p["has_base"]
                g.versions = versions
                g.version_params = p.get("version_params", [None] * len(versions))
                while len(g.version_params) < len(versions):
                    g.version_params.append(None)
                self.part_groups.append(g)
            
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
                                     font=('Segoe UI', 9, 'bold'), width=8)
        self.active_lbl.pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(ctrl, orient='vertical').pack(side=tk.LEFT, fill=tk.Y, padx=6)
        
        self.preset_lbl = ttk.Label(ctrl, text="", foreground='#aaa', font=('Consolas', 8))
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
        ttk.Label(time_frame, text=tr("Ctrl+wheel=zoom  Shift+wheel=scroll  wheel(R)=version  I=marker  2xclick=bounds"), 
                  foreground='gray', font=('Segoe UI', 8)).pack(side=tk.LEFT, padx=15)
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
        self.zoom = max(1.0, min(200.0, self.zoom * (1.25 if e.delta > 0 else 0.8)))
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
                # Клик -> курсор со snap
                self.cursor_pos = self._snap_to_points(self.sel_start, width)
                self.sel_start = self.sel_end = None
            else:
                # Snap границ выделения
                s1, s2 = sorted([self.sel_start, self.sel_end])
                s1 = self._snap_to_points(s1, width)
                s2 = self._snap_to_points(s2, width)
                self.sel_start, self.sel_end = s1, s2
        
        self._drag_mode = None
        self._redraw()
        self._update_time()

    def _snap_to_points(self, sample, width, snap_to_markers=True, snap_to_selection=False):
        """Примагничивание к частям, маркерам и/или выделению"""
        if self.total_samples == 0 or width <= 0:
            return sample
        
        samples_per_px = self.total_samples / self.zoom / width
        threshold = max(1, int(SNAP_THRESHOLD_PX * samples_per_px))
        
        snap_points = []
        for g in self.part_groups:
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
        """Шаг перемещения курсора стрелками"""
        if self.total_samples == 0:
            return 0
        visible = int(self.total_samples / self.zoom)
        return max(1, visible // (20 if large else 200))
    
    def _move_cursor(self, delta):
        if self.source_audio is None:
            return
        
        if self._is_playing:
            new_pos = max(self._play_start, min(self._play_end - 1, self._play_pos + delta))
            self._play_pos = new_pos
            self.play_pos = new_pos
        else:
            pos = self.cursor_pos if self.cursor_pos is not None else 0
            pos = max(0, min(self.total_samples - 1, pos + delta))
            self.cursor_pos = pos
            self.sel_start = self.sel_end = None
            self._redraw()
            self._update_time()
    
    def _hotkey_left(self, e=None):
        try:
            if self.parent.master.index(self.parent.master.select()) != 0:
                return
        except:
            pass
        self._move_cursor(-self._get_cursor_step())
        return "break"
    
    def _hotkey_right(self, e=None):
        try:
            if self.parent.master.index(self.parent.master.select()) != 0:
                return
        except:
            pass
        self._move_cursor(self._get_cursor_step())
        return "break"
    
    def _hotkey_shift_left(self, e=None):
        try:
            if self.parent.master.index(self.parent.master.select()) != 0:
                return
        except:
            pass
        self._move_cursor(-self._get_cursor_step(large=True))
        return "break"
    
    def _hotkey_shift_right(self, e=None):
        try:
            if self.parent.master.index(self.parent.master.select()) != 0:
                return
        except:
            pass
        self._move_cursor(self._get_cursor_step(large=True))
        return "break"

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
        
        if not part.delete_current():
            return "break"
        
        if part.has_base and len(part.versions) == 1:
            base_data = part.get_base_data()
            if base_data is not None:
                exp_len = part.end - part.start
                if len(base_data) != exp_len:
                    tmp = np.zeros(exp_len, dtype=np.float32)
                    tmp[:min(len(base_data), exp_len)] = base_data[:exp_len]
                    base_data = tmp
                self.result_audio[part.start:part.end] = base_data
                self.result_audio_display[part.start:part.end] = base_data
            
            part.cleanup()
            self.part_groups.remove(part)
            self._save_project()
            self.log(tr("Part deleted, data restored"))
            self._redraw()
            self._play_after_action(pos, end)
            return "break"
        
        self._apply_version(part)
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
        self._save_project()
        
        params_str = part.format_params(part.active_idx)
        label = part.version_label(part.active_idx)
        self.log(f"{label}: {params_str}" if params_str else label)
        
        self._active_track = 'result'
        self._update_active_label()
        
        if not self._stream_active:
            self._init_stream()
        
        pos = self.cursor_pos or 0
        if not (part.start <= pos < part.end):
            pos = part.start
        
        self._play_pos = self._play_start = pos
        self._play_end = part.end
        self._is_playing = True
        self.play_btn.config(text="⏸")
    
    def _apply_version(self, group, preserve_nested=False):
        data = group.get_data()
        if data is None:
            return
        
        # Записываем только реальные данные (без padding нулями)
        max_len = group.end - group.start
        write_len = min(len(data), max_len)
        if write_len <= 0:
            self._redraw()
            return
        
        write_data = data[:write_len]
        write_end = group.start + write_len
        
        if preserve_nested:
            nested = self._get_nested_parts(group)
            if nested:
                occupied = sorted([(n.start - group.start, n.end - group.start) for n in nested])
                current = 0
                for occ_start, occ_end in occupied:
                    seg_end = min(occ_start, write_len)
                    if current < seg_end:
                        abs_s = group.start + current
                        abs_e = group.start + seg_end
                        self.result_audio[abs_s:abs_e] = write_data[current:seg_end]
                        self.result_audio_display[abs_s:abs_e] = write_data[current:seg_end]
                    current = max(current, occ_end)
                if current < write_len:
                    abs_s = group.start + current
                    self.result_audio[abs_s:write_end] = write_data[current:]
                    self.result_audio_display[abs_s:write_end] = write_data[current:]
            else:
                self.result_audio[group.start:write_end] = write_data
                self.result_audio_display[group.start:write_end] = write_data
        else:
            self.result_audio[group.start:write_end] = write_data
            self.result_audio_display[group.start:write_end] = write_data
        
        self._redraw()

    def _get_nested_parts(self, part):
        """Найти части, полностью вложенные в данную"""
        return [g for g in self.part_groups 
                if g.id != part.id and g.start >= part.start and g.end <= part.end]

    def _is_replace_all_mode(self):
        try:
            import ctypes
            return ctypes.windll.user32.GetKeyState(0x14) & 1  # Caps Lock state
        except:
            return False

    def _ask_nested_action(self, part):
        """Caps Lock ON = заменить всё, OFF = сохранить вложенные"""
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
        menu.add_command(label=tr("Delete part files"), command=lambda: self._delete_part_files(part))
        
        if len(self.part_groups) > 1:
            menu.add_separator()
            menu.add_command(label=tr("Flatten to single file"), command=self._flatten_parts)
        
        menu.tk_popup(e.x_root, e.y_root)
    
    def _set_version(self, part, idx):
        proceed, preserve_nested = self._ask_nested_action(part)
        if not proceed:
            return
        
        part.active_idx = idx
        self._apply_version(part, preserve_nested)
        self._save_project()
        label = part.version_label(idx)
        params_str = part.format_params(idx)
        self.log(f"{label}: {params_str}" if params_str else label)
    
    def _delete_version(self, part):
        if part.delete_current():
            self._apply_version(part)
            self._save_project()
            self.log(f"{tr('Version deleted')} → {part.version_label(part.active_idx)}")
            self._redraw()
    
    def _delete_others(self, part):
        part.delete_others()
        self._save_project()
        self.log(tr("Other versions deleted"))
        self._redraw()
    
    def _delete_part(self, part):
        if part.has_base:
            base_data = part.get_base_data()
            if base_data is not None:
                exp_len = part.end - part.start
                if len(base_data) != exp_len:
                    tmp = np.zeros(exp_len, dtype=np.float32)
                    tmp[:min(len(base_data), exp_len)] = base_data[:exp_len]
                    base_data = tmp
                self.result_audio[part.start:part.end] = base_data
                self.result_audio_display[part.start:part.end] = base_data
        
        part.cleanup()
        self.part_groups.remove(part)
        self._save_project()
        self.log(tr("Part deleted, data restored"))
        self._redraw()
    
    def _delete_part_files(self, part):
        part.cleanup()
        self.part_groups.remove(part)
        self._save_project()
        self.log(tr("Part files deleted"))
        self._redraw()
    
    def _flatten_parts(self):
        for part in self.part_groups:
            part.cleanup()
        self.part_groups = []
        self._save_project()
        self.log(tr("Parts flattened"))
        self._redraw()
    
    def _hotkey_marker(self, e=None):
        try:
            nb = self.parent.master
            if nb.index(nb.select()) != 0: return
        except: pass
        
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
                self._save_project()
                self.log(f"{tr('Markers:')} {s1/self.sr:.2f}s, {s2/self.sr:.2f}s")
                self._redraw()
            return "break"
        
        if self.cursor_pos is not None:
            self._add_marker(self.cursor_pos)
        return "break"
    
    def _add_marker(self, sample):
        if sample in self.markers: return
        self.markers.append(sample)
        self.markers.sort()
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
        if 0 <= idx < len(self.markers):
            m = self.markers.pop(idx)
            self._save_project()
            self.log(f"{tr('Marker deleted:')} {m/self.sr:.2f}s")
            self._redraw()
    
    def _clear_markers(self):
        self.markers.clear()
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
        self.result_wf.draw()
        if self.play_pos is not None or self.source_wf._last_playhead_x is not None:
            self.source_wf.update_playhead()
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
        
    def _hotkey_play(self, e=None):
        try:
            nb = self.parent.master
            if nb.index(nb.select()) == 0:
                self._toggle_play()
                return "break"
        except: pass
        
    def _hotkey_number(self, e):
        try:
            nb = self.parent.master
            if nb.index(nb.select()) != 0:
                return
        except:
            pass
        
        if self.source_audio is None or not self.part_groups:
            return "break"
        
        num = int(e.char)
        pos = self.cursor_pos or 0
        
        matching = [g for g in self.part_groups if g.start <= pos < g.end]
        if not matching:
            return "break"
        part = min(matching, key=lambda g: g.size())
        
        if num == 0:
            if not part.has_base:
                return "break"
            target_idx = 0
        else:
            target_idx = num if part.has_base else num - 1
            if target_idx >= len(part.versions) or target_idx < 0:
                return "break"
        
        if target_idx == part.active_idx:
            return "break"
        
        proceed, preserve_nested = self._ask_nested_action(part)
        if not proceed:
            return "break"
        
        part.active_idx = target_idx
        self._apply_version(part, preserve_nested)
        self._save_project()
        self._active_track = 'result'
        self._update_active_label()
        
        label = part.version_label(part.active_idx)
        params_str = part.format_params(part.active_idx)
        self.log(f"{label}: {params_str}" if params_str else label)
        
        if not self._stream_active:
            self._init_stream()
        self._play_pos = self._play_start = pos
        self._play_end = part.end
        self._is_playing = True
        self.play_btn.config(text="⏸")
        
        return "break"
            
    def _hotkey_convert(self, e=None):
        try:
            nb = self.parent.master
            if nb.index(nb.select()) == 0:
                self._convert()
                return "break"
        except: pass
            
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
                
                import soundfile as sf
                project_dir = self._get_project_dir()
                tmp_dir = project_dir if project_dir else self.get_output_dir()
                if project_dir:
                    os.makedirs(project_dir, exist_ok=True)
                
                tmp_in = os.path.join(tmp_dir, "_temp_in.wav")
                tmp_out = os.path.join(tmp_dir, "_temp_out.wav")
                
                # ВАЖНО: source_audio для конвертации (НЕ source_audio_display!)
                sf.write(tmp_in, self._get_source_for_convert(start, end), self.sr)
                
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
                    
                    first_convert = self.result_audio is None
                    
                    if self.result_audio is None or len(self.result_audio) != self.total_samples:
                        self.result_audio = np.zeros(self.total_samples, dtype=np.float32)
                        self.result_audio_display = np.zeros(self.total_samples, dtype=np.float32)
                    
                    # Записываем только реальные данные без padding нулями
                    exp_len = end - start
                    write_len = min(len(converted), exp_len)
                    write_data = converted[:write_len]
                    
                    group = self._find_group(start, end)
                    if group is None:
                        group = PartGroup(start, end, self._get_parts_dir(), self.sr)
                        self.part_groups.append(group)
                        
                        if not first_convert:
                            existing = self.result_audio[start:end].copy()
                            if np.any(existing != 0):
                                group.set_base(existing)
                    
                    self.result_audio[start:start + write_len] = write_data
                    self.result_audio_display[start:start + write_len] = write_data
                    
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
                    
                    self._active_track = 'result'
                    
                    self.parent.after(0, self._update_active_label)
                    self.parent.after(0, self._redraw)
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