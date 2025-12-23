import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
import threading
import time
import uuid
import json

from lang import tr


class PartGroup:
    
    def __init__(self, start, end, parts_dir, sr):
        self.id = uuid.uuid4().hex[:8]
        self.start = start
        self.end = end
        self.parts_dir = parts_dir
        self.sr = sr
        self.versions = []
        self.active_idx = 0
        self.level = 0
        self.has_base = False
        self.created_at = time.time()
    
    def set_base(self, audio_data):
        if self.versions:
            return
        import soundfile as sf
        path = os.path.join(self.parts_dir, f"{self.id}_base.wav")
        sf.write(path, audio_data, self.sr)
        self.versions.append(path)
        self.has_base = True
        self.active_idx = 0
    
    def add_version(self, audio_data):
        import soundfile as sf
        idx = len(self.versions)
        path = os.path.join(self.parts_dir, f"{self.id}_v{idx}.wav")
        sf.write(path, audio_data, self.sr)
        self.versions.append(path)
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
        if self.has_base and self.versions:
            return self.get_data(0)
        return None
    
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
        try: os.remove(path)
        except: pass
        self.active_idx = min(self.active_idx, len(self.versions) - 1)
        return True
    
    def delete_others(self):
        if len(self.versions) <= 1:
            return
        keep = self.versions[self.active_idx]
        for p in self.versions:
            if p != keep:
                try: os.remove(p)
                except: pass
        self.versions = [keep]
        self.active_idx = 0
        self.has_base = False
    
    def cleanup(self):
        for p in self.versions:
            try: os.remove(p)
            except: pass
        self.versions = []
    
    def version_count(self):
        return len(self.versions) - (1 if self.has_base else 0)
    
    def version_label(self, idx):
        if self.has_base and idx == 0:
            return tr("Original")
        offset = 1 if self.has_base else 0
        return f"{tr('Version')} {idx - offset + 1}"
    
    def size(self):
        return self.end - self.start
    
    def to_dict(self):
        return {
            "id": self.id,
            "start": self.start,
            "end": self.end,
            "active_idx": self.active_idx,
            "has_base": self.has_base,
            "versions": [os.path.basename(v) for v in self.versions]
        }


MARKER_HANDLE_HEIGHT = 12
PART_ROW_HEIGHT = 11
PART_TOP_MARGIN = 2


class WaveformCanvas(tk.Canvas):
    
    def __init__(self, parent, editor, is_result=False, height=100, **kwargs):
        super().__init__(parent, height=height, bg='#1e1e2e', highlightthickness=0, bd=0, **kwargs)
        
        self.editor = editor
        self.is_result = is_result
        self.color = '#e74c3c' if is_result else '#5dade2'
        self._drag_marker = None
        
        self.bind('<Configure>', lambda e: self.draw())
        self.bind('<Button-1>', self._on_click)
        self.bind('<Double-Button-1>', self._on_double_click)
        self.bind('<B1-Motion>', self._on_drag)
        self.bind('<ButtonRelease-1>', self._on_release)
        self.bind('<Button-3>', self._on_right_click)
        self.bind('<MouseWheel>', self._on_wheel)
        self.bind('<Motion>', self._on_motion)
        self.bind('<Enter>', lambda e: self.focus_set())
        self.bind('<Leave>', lambda e: self.config(cursor=''))
        
    def get_audio(self):
        return self.editor.result_audio_display if self.is_result else self.editor.source_audio_display
    
    def _get_parts_zone_height(self):
        if not self.is_result or not self.editor.part_groups:
            return 0
        max_level = max((g.level for g in self.editor.part_groups), default=0)
        return PART_TOP_MARGIN + (max_level + 1) * PART_ROW_HEIGHT
    
    def _in_parts_zone(self, y):
        return self.is_result and y < self._get_parts_zone_height()
    
    def _in_marker_zone(self, y):
        return not self.is_result and y < MARKER_HANDLE_HEIGHT
        
    def draw(self):
        self.delete('all')
        w, h = self.winfo_width(), self.winfo_height()
        mid = h // 2
        ed = self.editor
        audio = self.get_audio()
        
        if audio is None or ed.total_samples == 0:
            self.create_text(w // 2, mid, text=tr("Result") if self.is_result else tr("Load WAV"), fill='#666')
            return
        
        visible = ed.total_samples / ed.zoom
        spp = visible / max(1, w)
        
        if ed.sel_start is not None:
            x1, x2 = ed._s2x(min(ed.sel_start, ed.sel_end), w), ed._s2x(max(ed.sel_start, ed.sel_end), w)
            self.create_rectangle(x1, 0, x2, h, fill='#2d4a6f', outline='#4a7ab0')
        
        for x in range(w):
            s0 = int(ed.offset + x * spp)
            s1 = min(int(ed.offset + (x + 1) * spp), len(audio))
            if s0 >= len(audio):
                break
            chunk = audio[s0:s1]
            if len(chunk):
                amp = np.max(np.abs(chunk))
                y = int(amp * mid * 0.9)
                self.create_line(x, mid - y, x, mid + y, fill=self.color)
        
        self.create_line(0, mid, w, mid, fill='#444')
        
        if not self.is_result:
            for i, marker in enumerate(ed.markers):
                mx = ed._s2x(marker, w)
                if 0 <= mx <= w:
                    self.create_line(mx, 0, mx, h, fill='#ff9800', width=2, dash=(4, 2))
                    self.create_rectangle(mx-4, 0, mx+4, MARKER_HANDLE_HEIGHT, 
                                          fill='#ff9800', outline='#e65100', tags=f'marker_{i}')
        
        if self.is_result and ed.part_groups:
            ed._assign_levels()
            for g in ed.part_groups:
                gx1, gx2 = ed._s2x(g.start, w), ed._s2x(g.end, w)
                if gx2 < 0 or gx1 > w:
                    continue
                
                y1 = PART_TOP_MARGIN + g.level * PART_ROW_HEIGHT
                y2 = y1 + PART_ROW_HEIGHT - 2
                
                if g.has_base and g.active_idx == 0:
                    fill, outline = '#566573', '#444'
                elif len(g.versions) > (2 if g.has_base else 1):
                    fill, outline = '#9b59b6', '#8e44ad'
                else:
                    fill, outline = '#7f8c8d', '#566573'
                
                x1_c, x2_c = max(0, gx1), min(w, gx2)
                self.create_rectangle(x1_c, y1, x2_c, y2, fill=fill, outline=outline)
                
                if (x2_c - x1_c) > 30:
                    cx = (x1_c + x2_c) // 2
                    if g.has_base:
                        txt = tr("base") if g.active_idx == 0 else f"{g.active_idx}/{len(g.versions)-1}"
                    else:
                        txt = f"{g.active_idx+1}/{len(g.versions)}" if len(g.versions) > 1 else ""
                    if txt:
                        self.create_text(cx, (y1 + y2) // 2, text=txt, fill='#fff', font=('Consolas', 7))
        
        if ed.part_groups:
            drawn = set()
            for g in ed.part_groups:
                for b in [g.start, g.end]:
                    if b not in drawn:
                        drawn.add(b)
                        bx = ed._s2x(b, w)
                        if 0 <= bx <= w:
                            self.create_line(bx, 0, bx, h, fill='#8e44ad', width=1, dash=(2, 2))
        
        if ed.play_pos is not None and 0 <= ed.play_pos < ed.total_samples:
            px = ed._s2x(ed.play_pos, w)
            if 0 <= px <= w:
                self.create_line(px, 0, px, h, fill='#00ff00', width=2)
        
        if ed.cursor_pos is not None:
            cx = ed._s2x(ed.cursor_pos, w)
            if 0 <= cx <= w:
                self.create_line(cx, 0, cx, h, fill='#ffff00', width=1, dash=(3, 3))
    
    def _find_marker_at(self, x, threshold=8):
        w = self.winfo_width()
        for i, m in enumerate(self.editor.markers):
            mx = self.editor._s2x(m, w)
            if abs(x - mx) <= threshold:
                return i
        return None
    
    def _find_part_at(self, x, y):
        if not self.is_result:
            return None
        w = self.winfo_width()
        sample = self.editor._x2s(x, w)
        for g in self.editor.part_groups:
            y1 = PART_TOP_MARGIN + g.level * PART_ROW_HEIGHT
            y2 = y1 + PART_ROW_HEIGHT
            if y1 <= y < y2 and g.start <= sample < g.end:
                return g
        return None
    
    def _on_motion(self, e):
        ed = self.editor
        if not self.is_result and self._in_marker_zone(e.y):
            if self._find_marker_at(e.x) is not None:
                self.config(cursor='sb_h_double_arrow')
                return
        if self._in_parts_zone(e.y):
            if self._find_part_at(e.x, e.y) is not None:
                self.config(cursor='hand2')
                return
        if ed.sel_start is not None:
            w = self.winfo_width()
            s1, s2 = sorted([ed.sel_start, ed.sel_end])
            xl, xr = ed._s2x(s1, w), ed._s2x(s2, w)
            if abs(e.x - xl) < 6 or abs(e.x - xr) < 6:
                self.config(cursor='sb_h_double_arrow')
                return
        self.config(cursor='')
            
    def _on_wheel(self, e):
        if e.state & 0x4:
            self.editor._on_zoom(e, self.winfo_width())
        elif e.state & 0x1:
            self.editor._on_scroll(e, self.winfo_width())
        elif self.is_result:
            sample = self.editor._x2s(e.x, self.winfo_width())
            self.editor._switch_version_at(sample, 1 if e.delta > 0 else -1)
        
    def _on_click(self, e):
        ed = self.editor
        w = self.winfo_width()
        if not self.is_result and self._in_marker_zone(e.y):
            marker_idx = self._find_marker_at(e.x)
            if marker_idx is not None:
                self._drag_marker = marker_idx
                return
        ed._on_click(e, w, self.is_result)
        
    def _on_double_click(self, e):
        self.editor._on_double_click(e, self.winfo_width(), self.is_result)
        
    def _on_drag(self, e):
        w = self.winfo_width()
        if self._drag_marker is not None:
            sample = max(0, min(self.editor.total_samples - 1, self.editor._x2s(e.x, w)))
            self.editor.markers[self._drag_marker] = sample
            self.editor._redraw()
            return
        self.editor._on_drag(e, w)
        
    def _on_release(self, e):
        if self._drag_marker is not None:
            self.editor.markers.sort()
            self._drag_marker = None
            self.editor._redraw()
            self.editor._save_project()
            return
        self.editor._on_release()
    
    def _on_right_click(self, e):
        w = self.winfo_width()
        if not self.is_result and self._in_marker_zone(e.y):
            marker_idx = self._find_marker_at(e.x)
            if marker_idx is not None:
                self.editor._show_marker_menu(e, marker_idx)
                return
        if self._in_parts_zone(e.y):
            part = self._find_part_at(e.x, e.y)
            if part is not None:
                self.editor._show_part_menu(e, part)
                return
        self.editor._switch_track_and_play(self.is_result, e.x, w)


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
        
        self.output_device = None
        self.output_devices = []
        
        self._build()
        self._scan_devices()
        
        parent.winfo_toplevel().bind('<r>', self._hotkey_convert)
        parent.winfo_toplevel().bind('<space>', self._hotkey_play)
        parent.winfo_toplevel().bind('<i>', self._hotkey_marker)
        parent.winfo_toplevel().bind('<I>', self._hotkey_marker)
        
        for i in range(10):
            parent.winfo_toplevel().bind(f'<Key-{i}>', self._hotkey_number)
    
    def _to_mono(self, audio):
        if audio is None:
            return None
        return audio.mean(axis=1).astype(np.float32) if len(audio.shape) > 1 else audio.astype(np.float32)
    
    def _get_project_dir(self):
        if not self.source_path:
            return None
        name = os.path.splitext(os.path.basename(self.source_path))[0]
        return os.path.join(self.get_output_dir(), "editor", name)
    
    def _get_parts_dir(self):
        project_dir = self._get_project_dir()
        if project_dir:
            d = os.path.join(project_dir, "parts")
        else:
            d = os.path.join(self.get_output_dir(), "editor", "_temp", "parts")
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
                self.part_groups.append(g)
            
            self.log(tr("Project loaded"))
            return True
            
        except Exception as e:
            self.log(f"{tr('Project load error:')} {e}")
            return False
    
    def _clear_parts(self):
        self.part_groups = []
    
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
        
    def _on_release(self):
        if self.sel_start is not None and abs(self.sel_end - self.sel_start) < 100:
            self.cursor_pos = self.sel_start
            self.sel_start = self.sel_end = None
            self._redraw()
        self._drag_mode = None
        self._update_time()
    
    def _find_group(self, start, end):
        for g in self.part_groups:
            if g.start == start and g.end == end:
                return g
        return None
    
    def _get_group_at(self, sample):
        matching = [g for g in self.part_groups if g.start <= sample < g.end]
        if not matching:
            return None
        return max(matching, key=lambda g: g.level)
    
    def _switch_version_at(self, sample, delta):
        g = self._get_group_at(sample)
        if g and g.switch(delta):
            self._apply_version(g)
            self._save_project()
            self.log(f"{g.version_label(g.active_idx)}")
    
    def _apply_version(self, group):
        data = group.get_data()
        if data is None: return
        exp_len = group.end - group.start
        if len(data) != exp_len:
            tmp = np.zeros(exp_len, dtype=np.float32)
            tmp[:min(len(data), exp_len)] = data[:exp_len]
            data = tmp
        self.result_audio[group.start:group.end] = data
        self.result_audio_display[group.start:group.end] = data
        self._redraw()
    
    def _show_part_menu(self, e, part):
        menu = tk.Menu(self.parent, tearoff=0)
        
        dur = (part.end - part.start) / self.sr
        menu.add_command(label=f"{part.start/self.sr:.1f}s - {part.end/self.sr:.1f}s ({dur:.2f}s)", state='disabled')
        menu.add_separator()
        
        for i in range(len(part.versions)):
            lbl = f"{'● ' if i == part.active_idx else '  '}{part.version_label(i)}"
            menu.add_command(label=lbl, command=lambda idx=i, p=part: self._set_version(p, idx))
        
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
        part.active_idx = idx
        self._apply_version(part)
        self._save_project()
        self.log(f"{part.version_label(idx)}")
    
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
        
    def _update_time(self):
        if not self.sr: return
        def fmt(s): 
            sec = s / self.sr
            return f"{int(sec // 60):02d}:{sec % 60:06.3f}"
        self.time_lbl.config(text=f"{fmt(self.cursor_pos or 0)} / {fmt(self.total_samples)}")
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
            
            self._clear_parts()
            self.markers.clear()
            self.result_audio = None
            self.result_audio_display = None
            
            self.source_audio = data.astype(np.float32)
            self.is_stereo = len(data.shape) > 1
            self.source_audio_display = self._to_mono(data)
            
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
        
        model_name = ""
        preset = self.get_preset_info()
        if preset.get("model"):
            model_name = os.path.splitext(preset["model"])[0]
        
        source_name = ""
        if self.source_path:
            source_name = os.path.splitext(os.path.basename(self.source_path))[0]
        
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
        if self.sr is None: return
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
                device=self.output_device, blocksize=256, latency='low'
            )
            self._stream.start()
            self._stream_active = True
            
            def updater():
                while self._stream_active:
                    if self._is_playing:
                        self.parent.after(0, self._redraw)
                        self.parent.after(0, self._sync_play_button)
                    time.sleep(0.03)
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
            if nb.index(nb.select()) != 0: return
        except: pass
        
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
            part.active_idx = 0
        else:
            target_idx = num if part.has_base else num - 1
            if target_idx >= len(part.versions) or target_idx < 0:
                return "break"
            part.active_idx = target_idx
        
        self._apply_version(part)
        self._save_project()
        self._active_track = 'result'
        self._update_active_label()
        self.log(f"{part.version_label(part.active_idx)}")
        
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
                if project_dir:
                    os.makedirs(project_dir, exist_ok=True)
                    tmp_dir = project_dir
                else:
                    tmp_dir = self.get_output_dir()
                
                tmp_in = os.path.join(tmp_dir, "_temp_in.wav")
                tmp_out = os.path.join(tmp_dir, "_temp_out.wav")
                
                # ВАЖНО: используем source_audio для конвертации
                sf.write(tmp_in, self.source_audio[start:end].copy(), self.sr)
                
                self.parent.after(0, lambda: self.log(f"{tr('Converting')} {(end-start)/self.sr:.2f}s..."))
                self.set_progress(30, tr("Conversion..."))
                
                if conv.convert(tmp_in, tmp_out, **params) and os.path.exists(tmp_out):
                    converted, csr = sf.read(tmp_out)
                    converted = converted.astype(np.float32)
                    
                    if csr != self.sr:
                        import librosa
                        converted = librosa.resample(converted, orig_sr=csr, target_sr=self.sr)
                    
                    first_convert = self.result_audio is None
                    
                    if self.result_audio is None or len(self.result_audio) != self.total_samples:
                        self.result_audio = np.zeros(self.total_samples, dtype=np.float32)
                        self.result_audio_display = np.zeros(self.total_samples, dtype=np.float32)
                    
                    exp_len = end - start
                    if len(converted) != exp_len:
                        tmp = np.zeros(exp_len, dtype=np.float32)
                        tmp[:min(len(converted), exp_len)] = converted[:exp_len]
                        converted = tmp
                    
                    group = self._find_group(start, end)
                    if group is None:
                        group = PartGroup(start, end, self._get_parts_dir(), self.sr)
                        self.part_groups.append(group)
                        
                        if not first_convert:
                            existing = self.result_audio[start:end].copy()
                            if np.any(existing != 0):
                                group.set_base(existing)
                    
                    self.result_audio[start:end] = converted
                    self.result_audio_display[start:end] = converted
                    
                    group.add_version(converted)
                    
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