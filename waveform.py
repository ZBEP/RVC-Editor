import tkinter as tk
import numpy as np
import math
from PIL import Image, ImageDraw, ImageTk

from lang import tr

MARKER_HANDLE_HEIGHT = 12
PART_ROW_HEIGHT = 11
PART_TOP_MARGIN = 2

class TimeRulerCanvas(tk.Canvas):

    def __init__(self, parent, editor, height=24, **kwargs):
        super().__init__(
            parent,
            height=height,
            bg='#d9d9d9',
            highlightthickness=0,
            bd=0,
            **kwargs
        )
        self.editor = editor
        self._cache_key = None
        self.bind('<Configure>', lambda e: self.draw())

    def _nice_step(self, x):
        if x <= 0:
            return 1.0
        p = 10 ** math.floor(math.log10(x))
        f = x / p
        if f <= 1:
            n = 1
        elif f <= 2:
            n = 2
        elif f <= 5:
            n = 5
        else:
            n = 10
        return n * p

    def _choose_major_step(self, span_sec, width):
        width = max(1, int(width))
        span_sec = max(span_sec, 1e-9)
        approx_ticks = max(2, int(width / 90))
        raw = span_sec / approx_ticks
        step = self._nice_step(raw)
        return max(step, 1.0 / max(1, int(getattr(self.editor, "sr", 44100) or 44100)))

    def _format_time(self, t, step):
        if step >= 1:
            total = int(round(t))
            s = total % 60
            m_total = total // 60
            m = m_total % 60
            h = m_total // 60
            if h > 0:
                return f"{h}:{m:02d}:{s:02d}"
            return f"{m_total}:{s:02d}"

        dec = 1 if step >= 0.1 else (2 if step >= 0.01 else 3)
        total_ms = int(round(t * 1000))
        ms = total_ms % 1000
        sec_total = total_ms // 1000
        s = sec_total % 60
        m_total = sec_total // 60
        frac = f"{ms:03d}"[:dec]

        if m_total > 0:
            return f"{m_total}:{s:02d}.{frac}"
        return f"{s}.{frac}"

    def draw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or h <= 1:
            return

        ed = self.editor
        sr = getattr(ed, "sr", None)
        total = int(getattr(ed, "total_samples", 0) or 0)
        zoom = float(getattr(ed, "zoom", 1.0) or 1.0)
        offset = int(getattr(ed, "offset", 0) or 0)

        key = (
            w, h, sr, total,
            round(zoom, 6), offset,
            getattr(ed, "sel_start", None), getattr(ed, "sel_end", None),
            getattr(ed, "cursor_pos", None)
        )
        if key == self._cache_key:
            return
        self._cache_key = key

        BG = '#d9d9d9'
        BORDER = '#b0b0b0'
        MAJOR = '#4f4f4f'
        MINOR = '#7a7a7a'
        TEXT = '#111111'
        SEL = '#b7d5ff'
        CUR = '#b58900'

        self.delete('all')
        self.create_rectangle(0, 0, w, h, fill=BG, outline='')

        self.create_line(0, h - 1, w, h - 1, fill=BORDER)

        if not sr or total <= 0:
            return

        visible = int(total / max(1e-9, zoom))
        visible = max(1, visible)

        span_sec = visible / sr
        start_s = offset / sr
        end_s = (offset + visible) / sr

        if getattr(ed, "sel_start", None) is not None:
            s1, s2 = sorted([ed.sel_start, ed.sel_end])
            x1 = max(0, min(w, ed._s2x(s1, w)))
            x2 = max(0, min(w, ed._s2x(s2, w)))
            if x2 > x1:
                self.create_rectangle(x1, 0, x2, h, fill=SEL, outline='')

        major = self._choose_major_step(span_sec, w)
        div = 5 if major >= 0.5 else 4
        minor = major / div

        t0 = math.floor(start_s / major) * major
        t = t0
        limit = 0
        while t <= end_s + major + 1e-9 and limit < 20000:
            limit += 1

            if start_s - 1e-9 <= t <= end_s + 1e-9:
                x = int(round((t - start_s) / span_sec * w))
                if 0 <= x <= w:
                    self.create_line(x, h - 1, x, h - 12, fill=MAJOR)

                    x_txt = x
                    anchor = 's'
                    if x < 20:
                        x_txt = x + 2
                        anchor = 'sw'
                    elif x > w - 20:
                        x_txt = x - 2
                        anchor = 'se'

                    self.create_text(
                        x_txt, h - 11,
                        text=self._format_time(t, major),
                        fill=TEXT,
                        font=('Segoe UI', 9, 'bold'),
                        anchor=anchor
                    )

            for i in range(1, div):
                tm = t + minor * i
                if tm < start_s - 1e-9 or tm > end_s + 1e-9:
                    continue
                x = int(round((tm - start_s) / span_sec * w))
                if 0 <= x <= w:
                    self.create_line(x, h - 1, x, h - 7, fill=MINOR)

            t += major

        cur = getattr(ed, "cursor_pos", None)
        if cur is not None and total > 0:
            cx = ed._s2x(cur, w)
            if 0 <= cx <= w:
                self.create_line(cx, 0, cx, h, fill=CUR, width=1)

class WaveformCanvas(tk.Canvas):

    def __init__(self, parent, editor, is_result=False, height=100, **kwargs):
        super().__init__(parent, height=height, bg='#1e1e2e', highlightthickness=0, bd=0, **kwargs)

        self.editor = editor
        self.is_result = is_result
        self.color = '#e74c3c' if is_result else '#5dade2'
        self._drag_marker = None
        self._drag_part_edge = None
        self._drag_start_data = None
        self._drag_part_move = None
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
        return (not self.is_result) and (y < MARKER_HANDLE_HEIGHT)

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

        audio_id = id(audio) if audio is not None else None
        audio_len = len(audio) if audio is not None else 0
        cache_key = (w, h, round(ed.zoom, 6), ed.offset, audio_id, audio_len)
        
        if cache_key == self._wf_cache_key and self._wf_image_id:
            return

        self._wf_cache_key = cache_key
        
        pixels = np.zeros((h, w, 3), dtype=np.uint8)
        pixels[:] = (30, 30, 30)
        
        mid = h // 2
        pixels[mid, :] = (68, 68, 68)
        
        if audio is not None and ed.total_samples > 0:
            visible = int(ed.total_samples / max(1e-9, ed.zoom))
            visible = max(1, visible)
            
            mipmap = ed.result_mipmap if self.is_result else ed.source_mipmap
            mn, mx = mipmap.get_envelope(audio, int(ed.offset), visible, w)
            
            if mn is not None and mx is not None:
                color = (231, 76, 60) if self.is_result else (93, 173, 226)
                scale = mid * 0.9
                if scale < 1:
                    scale = 1
                
                y_top = (mid - mx * scale).astype(int)
                y_bot = (mid - mn * scale).astype(int)
                swap = y_top > y_bot
                y_top[swap], y_bot[swap] = y_bot[swap], y_top[swap]
                
                for x in range(1, w):
                    if y_top[x] > y_bot[x-1] + 1:
                        y_top[x] = y_bot[x-1]
                    if y_bot[x] < y_top[x-1] - 1:
                        y_bot[x] = y_top[x-1]
                
                y_top = np.clip(y_top, 0, h - 1)
                y_bot = np.clip(y_bot, 0, h - 1)
                
                for x in range(w):
                    if y_bot[x] >= y_top[x]:
                        pixels[y_top[x]:y_bot[x] + 1, x] = color

        img = Image.fromarray(pixels, 'RGB')
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
            self.create_text(
                w // 2, mid,
                text=tr("Result") if self.is_result else tr("Load WAV"),
                fill='#666',
                tags='overlay'
            )
            return

        if ed.sel_start is not None:
            x1 = ed._s2x(min(ed.sel_start, ed.sel_end), w)
            x2 = ed._s2x(max(ed.sel_start, ed.sel_end), w)
            self.create_rectangle(
                x1, 0, x2, h,
                fill='#2d4a6f',
                outline='#4a7ab0',
                stipple='gray25',
                tags='overlay'
            )

        if not self.is_result:
            for i, marker in enumerate(ed.markers):
                mx = ed._s2x(marker, w)
                if 0 <= mx <= w:
                    self.create_line(mx, 0, mx, h, fill='#ff9800', width=2, dash=(4, 2), tags='overlay')
                    self.create_rectangle(
                        mx - 4, 0, mx + 4, MARKER_HANDLE_HEIGHT,
                        fill='#ff9800',
                        outline='#e65100',
                        tags=('overlay', f'marker_{i}')
                    )

        if self.is_result and ed.part_groups:
            ed._assign_levels()
            for g in ed.part_groups:
                gx1, gx2 = ed._s2x(g.start, w), ed._s2x(g.end, w)
                if gx2 < 0 or gx1 > w:
                    continue

                y1 = PART_TOP_MARGIN + g.level * PART_ROW_HEIGHT
                y2 = y1 + PART_ROW_HEIGHT - 2

                if (not g.has_base and len(g.versions) == 1) or (g.has_base and g.active_idx == 0):
                    fill, outline = '#303030', ''
                else:
                    fill, outline = '#9b59b6', ''

                x1_c, x2_c = max(0, gx1), min(w, gx2)
                self.create_rectangle(x1_c, y1, x2_c, y2, fill=fill, outline=outline, tags='overlay')

                if g.overwritten_ranges:
                    for abs_start, abs_end in g.overwritten_ranges:
                        ox1 = max(x1_c, ed._s2x(abs_start, w))
                        ox2 = min(x2_c, ed._s2x(abs_end, w))
                        if ox2 > ox1:
                            self.create_rectangle(ox1, y1, ox2, y2, fill='#303030', outline='', tags='overlay')

                if (x2_c - x1_c) > 10:
                    cx = (x1_c + x2_c) // 2
                    wide = (x2_c - x1_c) > 420
                    medium = (x2_c - x1_c) > 60
                    
                    if medium:
                        if g.has_base:
                            txt = tr("base") if g.active_idx == 0 else f"{g.active_idx}/{len(g.versions) - 1}"
                        else:
                            txt = f"{g.active_idx + 1}/{len(g.versions)}" if len(g.versions) > 1 else ""
                        
                        if wide:
                            params_str = g.format_params(g.active_idx)
                            if params_str:
                                txt = (txt + " " if txt else "") + "  " + params_str + "  "
                        
                        if g.volume_db != 0:
                            skip_vol = g.has_base and g.active_idx == 0 and len(g.versions) > 1
                            vol_str = f"({g.volume_db:+d} dB)" if skip_vol else f"{g.volume_db:+d} dB"
                            txt = (txt + " " if txt else "") + vol_str
                    else:
                        if g.has_base:
                            txt = "" if g.active_idx == 0 else str(g.active_idx)
                        else:
                            txt = str(g.active_idx + 1) if len(g.versions) > 1 else ""
                    
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
                            self.create_line(bx, 0, bx, h, fill='#8e44ad', width=1, dash=(2, 2), tags='overlay')

        if ed.cursor_pos is not None:
            cx = ed._s2x(ed.cursor_pos, w)
            if 0 <= cx <= w:
                self.create_line(cx, 0, cx, h, fill='#ffff00', width=1, dash=(3, 3), tags='overlay')

        if self.is_result:
            self.create_text(w - 6, 2, text="R", fill='#e6e6e6', font=('Consolas', 10, 'bold'),
                             anchor='ne', tags='overlay')
        else:
            self.create_text(w - 6, h - 4, text="S", fill='#e6e6e6', font=('Consolas', 10, 'bold'),
                             anchor='se', tags='overlay')

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
        candidates = []
        for g in self.editor.part_groups:
            y1 = PART_TOP_MARGIN + g.level * PART_ROW_HEIGHT
            y2 = y1 + PART_ROW_HEIGHT
            if not (y1 <= y < y2):
                continue
            start_x = self.editor._s2x(g.start, w)
            end_x = self.editor._s2x(g.end, w)
            if abs(x - start_x) <= threshold:
                candidates.append((g, 'start', start_x))
            if abs(x - end_x) <= threshold:
                candidates.append((g, 'end', end_x))

        if not candidates:
            return None
        if len(candidates) == 1:
            return (candidates[0][0], candidates[0][1])

        candidates.sort(key=lambda c: abs(x - c[2]))
        best_x = candidates[0][2]
        same_pos = [c for c in candidates if abs(c[2] - best_x) < 2]

        if len(same_pos) == 1:
            return (same_pos[0][0], same_pos[0][1])

        prefer = 'end' if x <= best_x else 'start'
        for c in same_pos:
            if c[1] == prefer:
                return (c[0], c[1])

        return (same_pos[0][0], same_pos[0][1])

    def _on_motion(self, e):
        ed = self.editor
        if self.is_result:
            if self._find_part_edge_at(e.x, e.y):
                self.config(cursor='sb_h_double_arrow')
                return
            if self._in_parts_zone(e.y) and self._find_part_at(e.x, e.y):
                self.config(cursor='fleur')
                return
        if (not self.is_result) and self._in_marker_zone(e.y):
            if self._find_marker_at(e.x) is not None:
                self.config(cursor='sb_h_double_arrow')
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
            if self._in_parts_zone(e.y):
                part = self._find_part_at(e.x, e.y)
                if part is not None:
                    sample = ed._x2s(e.x, w)
                    self._drag_part_move = {
                        "part": part,
                        "start_sample": sample,
                        "old_start": part.start,
                        "old_end": part.end,
                        "start_x": e.x,
                        "active": False
                    }
                    return
        if (not self.is_result) and self._in_marker_zone(e.y):
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
                self.editor._switch_version_and_play(part, -1 if e.delta > 0 else 1)
        elif self.is_result:
            sample = self.editor._x2s(e.x, self.winfo_width())
            self.editor._switch_version_at(sample, -1 if e.delta > 0 else 1)

    def _on_double_click(self, e):
        self.editor._on_double_click(e, self.winfo_width(), self.is_result)

    def _on_drag(self, e):
        w = self.winfo_width()
        MIN_PART_SIZE = 256
        DRAG_THRESHOLD = 10
        
        if self._drag_part_move is not None:
            data = self._drag_part_move
            if not data.get("active", False):
                if abs(e.x - data["start_x"]) < DRAG_THRESHOLD:
                    return
                data["active"] = True
                data["start_sample"] = self.editor._x2s(e.x, w)
            part = data["part"]
            current_sample = max(0, min(self.editor.total_samples - 1, self.editor._x2s(e.x, w)))
            delta = current_sample - data["start_sample"]
            new_start = data["old_start"] + delta
            new_end = data["old_end"] + delta
            part_size = data["old_end"] - data["old_start"]
            if new_start < 0:
                new_start = 0
                new_end = part_size
            if new_end > self.editor.total_samples:
                new_end = self.editor.total_samples
                new_start = new_end - part_size
            part.start = new_start
            part.end = new_end
            self.editor._redraw()
            return
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
        MIN_PART_SIZE = 256
        
        if self._drag_part_move is not None:
            data = self._drag_part_move
            if not data.get("active", False):
                part = data["part"]
                part.start = data["old_start"]
                part.end = data["old_end"]
                self._drag_part_move = None
                return
            part = data["part"]
            w = self.winfo_width()
            current_sample = max(0, min(ed.total_samples - 1, ed._x2s(e.x, w)))
            delta = current_sample - data["start_sample"]
            new_start = data["old_start"] + delta
            new_end = data["old_end"] + delta
            part_size = data["old_end"] - data["old_start"]
            
            if new_start < 0:
                new_start = 0
                new_end = part_size
            if new_end > ed.total_samples:
                new_end = ed.total_samples
                new_start = new_end - part_size
            
            snapped_start = ed._snap_to_points(new_start, w, snap_to_markers=True, snap_to_selection=True, exclude_part=part)
            snap_delta = snapped_start - new_start
            new_start = snapped_start
            new_end = new_end + snap_delta
            
            if new_end > ed.total_samples:
                new_end = ed.total_samples
                new_start = new_end - part_size
            if new_start < 0:
                new_start = 0
                new_end = part_size
            
            final_delta = new_start - data["old_start"]
            
            if final_delta != 0:
                part.start = new_start
                part.end = new_end
                ed._finalize_part_move(part, final_delta)
            else:
                part.start = data["old_start"]
                part.end = data["old_end"]
                ed._redraw()
            
            self._drag_part_move = None
            return
        
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
                ed._compute_overwritten_ranges()
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
        if (not self.is_result) and self._in_marker_zone(e.y):
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