import tkinter as tk
import numpy as np
from PIL import Image, ImageDraw, ImageTk

from lang import tr

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
        self._drag_part_edge = None
        self._drag_start_data = None
        self._last_playhead_x = None
        self._last_size = (0, 0)
        
        self._wf_photo = None
        self._wf_image_id = None
        self._wf_cache_key = None
        
        self.bind('<Configure>', self._on_configure)
        self.bind('<Button-1>', self._on_click)
        self.bind('<Double-Button-1>', self._on_double_click)
        self.bind('<B1-Motion>', self._on_drag)
        self.bind('<ButtonRelease-1>', self._on_release)
        self.bind('<Button-3>', self._on_right_click)
        self.bind('<MouseWheel>', self._on_wheel)
        self.bind('<Motion>', self._on_motion)
        self.bind('<Enter>', lambda e: self.focus_set())
        self.bind('<Leave>', lambda e: self.config(cursor=''))
        self.bind('<Delete>', self._on_delete)
    
    def _on_configure(self, e):
        new_size = (e.width, e.height)
        if new_size != self._last_size:
            self._last_size = new_size
            self._last_playhead_x = None
            self._wf_cache_key = None
            self.draw()
            self._draw_playhead()
        
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
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or h <= 1:
            return
        self._update_waveform_image(w, h)
        self.delete('overlay')
        self._draw_overlay(w, h)
    
    def _update_waveform_image(self, w, h):
        ed = self.editor
        audio = self.get_audio()
        
        if audio is None:
            cache_key = (w, h, None, None)
        else:
            cache_key = (w, h, ed.zoom, ed.offset)
        
        if cache_key == self._wf_cache_key and self._wf_image_id:
            return
        
        self._wf_cache_key = cache_key
        
        img = Image.new('RGB', (w, h), (30, 30, 46))
        
        if audio is not None and ed.total_samples > 0:
            draw = ImageDraw.Draw(img)
            mid = h // 2
            draw.line([(0, mid), (w, mid)], fill=(68, 68, 68))
            
            visible = ed.total_samples / ed.zoom
            spp = visible / max(1, w)
            audio_len = len(audio)
            color_rgb = (231, 76, 60) if self.is_result else (93, 173, 226)
            
            for x in range(w):
                s0 = int(ed.offset + x * spp)
                if s0 >= audio_len:
                    break
                s1 = min(int(ed.offset + (x + 1) * spp), audio_len)
                chunk = audio[s0:s1]
                if len(chunk):
                    amp = float(np.max(np.abs(chunk)))
                    y = int(amp * mid * 0.9)
                    if y > 0:
                        draw.line([(x, mid - y), (x, mid + y)], fill=color_rgb)
        
        self._wf_photo = ImageTk.PhotoImage(img)
        
        if self._wf_image_id:
            self.itemconfig(self._wf_image_id, image=self._wf_photo)
        else:
            self._wf_image_id = self.create_image(0, 0, anchor='nw', image=self._wf_photo, tags='waveform')
    
    def _draw_overlay(self, w, h):
        ed = self.editor
        audio = self.get_audio()
        mid = h // 2
        
        if audio is None or ed.total_samples == 0:
            self.create_text(w // 2, mid, text=tr("Result") if self.is_result else tr("Load WAV"), 
                           fill='#666', tags='overlay')
            return
        
        if ed.sel_start is not None:
            x1 = ed._s2x(min(ed.sel_start, ed.sel_end), w)
            x2 = ed._s2x(max(ed.sel_start, ed.sel_end), w)
            self.create_rectangle(x1, 0, x2, h, fill='#2d4a6f', outline='#4a7ab0', 
                                stipple='gray50', tags='overlay')
        
        if not self.is_result:
            for i, marker in enumerate(ed.markers):
                mx = ed._s2x(marker, w)
                if 0 <= mx <= w:
                    self.create_line(mx, 0, mx, h, fill='#ff9800', width=2, dash=(4, 2), tags='overlay')
                    self.create_rectangle(mx-4, 0, mx+4, MARKER_HANDLE_HEIGHT, 
                                        fill='#ff9800', outline='#e65100', tags=('overlay', f'marker_{i}'))
        
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
                self.create_rectangle(x1_c, y1, x2_c, y2, fill=fill, outline=outline, tags='overlay')
                
                if (x2_c - x1_c) > 30:
                    cx = (x1_c + x2_c) // 2
                    if g.has_base:
                        txt = tr("base") if g.active_idx == 0 else f"{g.active_idx}/{len(g.versions)-1}"
                    else:
                        txt = f"{g.active_idx+1}/{len(g.versions)}" if len(g.versions) > 1 else ""
                    if txt:
                        self.create_text(cx, (y1 + y2) // 2, text=txt, fill='#fff', 
                                       font=('Consolas', 7), tags='overlay')
        
        if ed.part_groups:
            drawn = set()
            for g in ed.part_groups:
                for b in (g.start, g.end):
                    if b not in drawn:
                        drawn.add(b)
                        bx = ed._s2x(b, w)
                        if 0 <= bx <= w:
                            self.create_line(bx, 0, bx, h, fill='#8e44ad', width=1, 
                                           dash=(2, 2), tags='overlay')
        
        if ed.cursor_pos is not None:
            cx = ed._s2x(ed.cursor_pos, w)
            if 0 <= cx <= w:
                self.create_line(cx, 0, cx, h, fill='#ffff00', width=1, dash=(3, 3), tags='overlay')
    
    def _draw_playhead(self):
        ed = self.editor
        self.delete('playhead')
        
        if ed.play_pos is None or ed.total_samples == 0:
            self._last_playhead_x = None
            return
        
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or h <= 1:
            return
            
        px = int(ed._s2x(ed.play_pos, w))
        self._last_playhead_x = px
        
        if 0 <= px <= w:
            self.create_line(px, 0, px, h, fill='#00ff00', width=2, tags='playhead')
    
    def update_playhead(self):
        ed = self.editor
        
        if ed.play_pos is None:
            if self._last_playhead_x is not None:
                self.delete('playhead')
                self._last_playhead_x = None
            return
        
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or h <= 1:
            return
            
        px = int(ed._s2x(ed.play_pos, w))
        
        if self._last_playhead_x == px:
            return
        
        self._last_playhead_x = px
        self.delete('playhead')
        
        if 0 <= px <= w:
            self.create_line(px, 0, px, h, fill='#00ff00', width=2, tags='playhead')
    
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
    
    def _find_part_edge_at(self, x, y, threshold=6):
        if not self.is_result or not self.editor.part_groups:
            return None
        w = self.winfo_width()
        for g in self.editor.part_groups:
            y1 = PART_TOP_MARGIN + g.level * PART_ROW_HEIGHT
            y2 = y1 + PART_ROW_HEIGHT
            if not (y1 <= y < y2):
                continue
            start_x = self.editor._s2x(g.start, w)
            end_x = self.editor._s2x(g.end, w)
            if abs(x - start_x) <= threshold:
                return (g, 'start')
            if abs(x - end_x) <= threshold:
                return (g, 'end')
        return None
    
    def _on_motion(self, e):
        ed = self.editor
        if self.is_result and self._find_part_edge_at(e.x, e.y):
            self.config(cursor='sb_h_double_arrow')
            return
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
    
    def _on_click(self, e):
        ed = self.editor
        w = self.winfo_width()
        if self.is_result:
            edge = self._find_part_edge_at(e.x, e.y)
            if edge is not None:
                part, edge_type = edge
                self._drag_start_data = {"part_id": part.id, "old_start": part.start, "old_end": part.end}
                self._drag_part_edge = edge
                return
        if not self.is_result and self._in_marker_zone(e.y):
            marker_idx = self._find_marker_at(e.x)
            if marker_idx is not None:
                self._drag_start_data = {"idx": marker_idx, "old_pos": ed.markers[marker_idx]}
                self._drag_marker = marker_idx
                return
        ed._on_click(e, w, self.is_result)
            
    def _on_wheel(self, e):
        if e.state & 0x4:
            self.editor._on_zoom(e, self.winfo_width())
        elif e.state & 0x1:
            self.editor._on_scroll(e, self.winfo_width())
        elif self.is_result and self._in_parts_zone(e.y):
            part = self._find_part_at(e.x, e.y)
            if part:
                self.editor._switch_version_and_play(part, 1 if e.delta > 0 else -1)
        elif self.is_result:
            sample = self.editor._x2s(e.x, self.winfo_width())
            self.editor._switch_version_at(sample, 1 if e.delta > 0 else -1)
        
    def _on_double_click(self, e):
        self.editor._on_double_click(e, self.winfo_width(), self.is_result)
        
    def _on_drag(self, e):
        w = self.winfo_width()
        MIN_PART_SIZE = 2000
        if self._drag_part_edge is not None:
            part, edge_type = self._drag_part_edge
            sample = max(0, min(self.editor.total_samples - 1, self.editor._x2s(e.x, w)))
            if edge_type == 'start':
                part.start = max(0, min(sample, part.end - MIN_PART_SIZE))
            else:
                part.end = min(self.editor.total_samples, max(sample, part.start + MIN_PART_SIZE))
            self.editor._redraw()
            return
        if self._drag_marker is not None:
            sample = max(0, min(self.editor.total_samples - 1, self.editor._x2s(e.x, w)))
            self.editor.markers[self._drag_marker] = sample
            self.editor._redraw()
            return
        self.editor._on_drag(e, w)
        
    def _on_release(self, e):
        ed = self.editor
        MIN_PART_SIZE = 2000
        
        if self._drag_part_edge is not None:
            part, edge_type = self._drag_part_edge
            w = self.winfo_width()
            
            sample = max(0, min(ed.total_samples - 1, ed._x2s(e.x, w)))
            snapped = ed._snap_to_points(sample, w, snap_to_markers=True, snap_to_selection=True, exclude_part=part)
            
            if edge_type == 'start':
                new_start = max(0, min(snapped, part.end - MIN_PART_SIZE))
                changed = part.start != new_start
                part.start = new_start
            else:
                new_end = min(ed.total_samples, max(snapped, part.start + MIN_PART_SIZE))
                changed = part.end != new_end
                part.end = new_end
            
            self._drag_part_edge = None
            self._drag_start_data = None
            
            if changed:
                ed._push_snapshot()
            ed._redraw()
            ed._save_project()
            return
        
        if self._drag_marker is not None:
            w = self.winfo_width()
            sample = max(0, min(ed.total_samples - 1, ed._x2s(e.x, w)))
            snapped = ed._snap_to_points(sample, w, snap_to_markers=False, snap_to_selection=True)
            
            old_pos = ed.markers[self._drag_marker]
            changed = snapped != old_pos
            
            ed.markers[self._drag_marker] = snapped
            ed.markers.sort()
            
            self._drag_marker = None
            self._drag_start_data = None
            
            if changed:
                ed._push_snapshot()
            ed._redraw()
            ed._save_project()
            return
        
        ed._on_release(self.winfo_width())
    
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

    def _on_delete(self, e=None):
        self.editor._hotkey_delete()
        return "break"