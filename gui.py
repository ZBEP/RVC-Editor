import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from config_app import (
    APP_DIR, RVC_ROOT, WEIGHTS_DIR, LOGS_DIR, INDEX_ROOT,
    INPUT_DIR, OUTPUT_DIR, DEFAULT_SETTINGS, AUDIO_EXTENSIONS,
    OUTPUT_FORMATS, F0_METHODS, CREPE_METHODS_WITH_HOP,
    load_settings, save_settings
)
from widgets import ScaleWithEntry, ResettableLabel, ToolTip
from presets import PRESET_KEYS, load_presets, save_presets, get_default_presets
from lang import tr


class RVCConverterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(tr("RVC Editor"))
        
        self.saved_settings = load_settings()
        self.presets = load_presets()
        
        self._restore_window_geometry()
        
        self.models_list = []
        self.indexes_list = []
        
        self._init_variables()
        
        os.makedirs(self._get_input_dir(), exist_ok=True)
        os.makedirs(self._get_output_dir(), exist_ok=True)
        
        self.converter = None
        self.is_converting = False
        self.editor = None
        self.preset_btns = {}
        
        self._create_widgets()
        self._scan_models()
        self._restore_model_selection()
        self._bind_hotkeys()
        
        self.model_path.trace_add("write", self._on_model_change)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self.root.after(200, lambda: self.editor and self.editor.on_tab_activated())
        
        if self.log_visible.get():
            self.root.after(100, lambda: self.log_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0)))
    
    def _init_variables(self):
        s = self.saved_settings
        self.model_path = tk.StringVar(value=s.get("model", ""))
        self.index_path = tk.StringVar(value=s.get("index", ""))
        self.input_dir = tk.StringVar(value=s.get("input_dir", INPUT_DIR))
        self.output_dir = tk.StringVar(value=s.get("output_dir", OUTPUT_DIR))
        
        self.pitch = tk.IntVar(value=s.get("pitch", 0))
        self.f0_method = tk.StringVar(value=s.get("f0_method", "rmvpe"))
        self.index_rate = tk.DoubleVar(value=s.get("index_rate", 0.90))
        self.filter_radius = tk.IntVar(value=s.get("filter_radius", 3))
        self.resample_sr = tk.IntVar(value=s.get("resample_sr", 0))
        self.rms_mix_rate = tk.DoubleVar(value=s.get("rms_mix_rate", 0.25))
        self.protect = tk.DoubleVar(value=s.get("protect", 0.33))
        self.output_format = tk.StringVar(value=s.get("output_format", "wav"))
        self.crepe_hop_length = tk.IntVar(value=s.get("crepe_hop_length", 120))
        
        self.log_visible = tk.BooleanVar(value=s.get("log_visible", False))
        
        self.preset_load_model = tk.BooleanVar(value=s.get("preset_load_model", False))
        self.preset_load_pitch = tk.BooleanVar(value=s.get("preset_load_pitch", False))
        self.preset_load_f0 = tk.BooleanVar(value=s.get("preset_load_f0", False))

    def _get_input_dir(self):
        val = self.input_dir.get().strip()
        return val if val else INPUT_DIR

    def _get_output_dir(self):
        val = self.output_dir.get().strip()
        return val if val else OUTPUT_DIR

    def _bind_hotkeys(self):
        for key in PRESET_KEYS:
            self.root.bind(f'<{key}>', lambda e, k=key: self._load_preset(k))
        self.root.bind('<Control-F1>', lambda e: self._toggle_preset_option('model'))
        self.root.bind('<Control-F2>', lambda e: self._toggle_preset_option('pitch'))
        self.root.bind('<Control-F3>', lambda e: self._toggle_preset_option('f0'))
    
    def _toggle_preset_option(self, option):
        if option == 'model':
            new_val = not self.preset_load_model.get()
            self.preset_load_model.set(new_val)
            self.log(f"{tr('Load model:')} {tr('ON') if new_val else tr('OFF')}")
        elif option == 'pitch':
            new_val = not self.preset_load_pitch.get()
            self.preset_load_pitch.set(new_val)
            self.log(f"{tr('Load pitch:')} {tr('ON') if new_val else tr('OFF')}")
        elif option == 'f0':
            new_val = not self.preset_load_f0.get()
            self.preset_load_f0.set(new_val)
            self.log(f"{tr('Load F0 method:')} {tr('ON') if new_val else tr('OFF')}")
    
    def _restore_window_geometry(self):
        geometry = self.saved_settings.get("window_geometry", "")
        state = self.saved_settings.get("window_state", "normal")
        self.root.geometry(geometry if geometry else "780x640")
        self.root.minsize(760, 620)
        if state == "zoomed":
            self.root.after(100, lambda: self.root.state('zoomed'))
    
    def _save_window_geometry(self):
        state = self.root.state()
        if state == 'zoomed':
            return "zoomed", self.saved_settings.get("window_geometry", "780x640+100+100")
        return "normal", self.root.geometry()
        
    def _restore_model_selection(self):
        saved_model = self.saved_settings.get("model", "")
        saved_index = self.saved_settings.get("index", "")
        if saved_model and saved_model in self.models_list:
            self.model_path.set(saved_model)
        elif self.models_list:
            self.model_path.set(self.models_list[0])
        if saved_index and saved_index in self.indexes_list:
            self.index_path.set(saved_index)
    
    def _on_tab_changed(self, event=None):
        try:
            current = self.notebook.index(self.notebook.select())
            if self.editor and hasattr(self, '_last_tab') and self._last_tab == 0 and current != 0:
                self.editor.on_tab_deactivated()
            if current == 0 and self.editor:
                self.editor.on_tab_activated()
            self._last_tab = current
        except:
            pass
    
    def _is_editor_active(self):
        try:
            return self.notebook.index(self.notebook.select()) == 0
        except:
            return False
        
    def _on_close(self):
        if self.editor:
            self.editor.cleanup()
        self._save_current_settings()
        self.root.destroy()
        
    def _save_current_settings(self):
        state, geometry = self._save_window_geometry()
        settings = {
            "model": self.model_path.get(),
            "index": self.index_path.get(),
            "input_dir": self.input_dir.get(),
            "output_dir": self.output_dir.get(),
            "pitch": self.pitch.get(),
            "f0_method": self.f0_method.get(),
            "index_rate": self.index_rate.get(),
            "filter_radius": self.filter_radius.get(),
            "resample_sr": self.resample_sr.get(),
            "rms_mix_rate": self.rms_mix_rate.get(),
            "protect": self.protect.get(),
            "crepe_hop_length": self.crepe_hop_length.get(),
            "output_format": self.output_format.get(),
            "log_visible": self.log_visible.get(),
            "window_geometry": geometry,
            "window_state": state,
            "editor_file": self.saved_settings.get("editor_file", ""),
            "preset_load_model": self.preset_load_model.get(),
            "preset_load_pitch": self.preset_load_pitch.get(),
            "preset_load_f0": self.preset_load_f0.get(),
            "blend_mode": self.editor.blend_mode if self.editor else 0,
            "crossfade_type": self.editor.crossfade_type if self.editor else 0
        }
        save_settings(settings)
        
    def _reset_all_params(self):
        d = DEFAULT_SETTINGS
        self.pitch.set(d["pitch"])
        self.f0_method.set(d["f0_method"])
        self.index_rate.set(d["index_rate"])
        self.filter_radius.set(d["filter_radius"])
        self.resample_sr.set(d["resample_sr"])
        self.rms_mix_rate.set(d["rms_mix_rate"])
        self.protect.set(d["protect"])
        self.crepe_hop_length.set(d["crepe_hop_length"])
        self.f0_other_combo.set("")
        self._update_f0_buttons()
        self._update_crepe_visibility()
        self.log(tr("Parameters reset"))
    
    def _set_editor_file(self, path):
        self.saved_settings["editor_file"] = path
        self._save_current_settings()
    
    def _get_preset_info_for_editor(self):
        return {
            "model": self.model_path.get(),
            "f0_method": self.f0_method.get(),
            "pitch": self.pitch.get(),
            "index_rate": self.index_rate.get(),
            "filter_radius": self.filter_radius.get(),
            "resample_sr": self.resample_sr.get(),
            "rms_mix_rate": self.rms_mix_rate.get(),
            "protect": self.protect.get(),
            "crepe_hop_length": self.crepe_hop_length.get()
        }
    
    def _get_current_preset_data(self):
        return {
            "model": self.model_path.get(),
            "index": self.index_path.get(),
            "pitch": self.pitch.get(),
            "f0_method": self.f0_method.get(),
            "index_rate": self.index_rate.get(),
            "filter_radius": self.filter_radius.get(),
            "resample_sr": self.resample_sr.get(),
            "rms_mix_rate": self.rms_mix_rate.get(),
            "protect": self.protect.get(),
            "crepe_hop_length": self.crepe_hop_length.get(),
            "output_format": self.output_format.get()
        }
    
    def _save_preset(self, key):
        if not self.model_path.get():
            self.log(tr("First select a model"))
            return
        self.presets[key] = self._get_current_preset_data()
        save_presets(self.presets)
        self.log(f"{tr('Preset')} {key} {tr('saved')}")
    
    def _load_preset(self, key):
        if key not in self.presets:
            self.log(f"{tr('Preset')} {key} {tr('is empty')}")
            return
        
        p = self.presets[key]
        need_reload = False
        
        if self.preset_load_model.get():
            new_model = p.get("model", "")
            new_index = p.get("index", "")
            if new_model and new_model in self.models_list:
                if new_model != self.model_path.get() or new_index != self.index_path.get():
                    need_reload = True
                self.model_path.set(new_model)
                if new_index:
                    self.index_path.set(new_index)
        
        if self.preset_load_pitch.get():
            self.pitch.set(p.get("pitch", 0))
        
        if self.preset_load_f0.get():
            f0_method = p.get("f0_method", "")
            if f0_method:
                self.f0_method.set(f0_method)
                self.crepe_hop_length.set(p.get("crepe_hop_length", 120))
        
        self.index_rate.set(p.get("index_rate", 0.9))
        self.filter_radius.set(p.get("filter_radius", 3))
        self.resample_sr.set(p.get("resample_sr", 0))
        self.rms_mix_rate.set(p.get("rms_mix_rate", 0.25))
        self.protect.set(p.get("protect", 0.33))
        self.output_format.set(p.get("output_format", "wav"))
        
        self._update_f0_buttons()
        self._update_crepe_visibility()
        
        if need_reload and self.converter and self.converter.is_initialized:
            self.log(f"{tr('Preset')} {key}: {tr('reloading model...')}")
            self._ensure_model_loaded()
        else:
            self.log(f"{tr('Preset')} {key} {tr('loaded')}")
        
        if self._is_editor_active() and self.editor:
            self.editor.on_preset_loaded()
    
    def _reset_presets(self):
        self.presets = get_default_presets()
        save_presets(self.presets)
        self.log(tr("Presets reset to default"))
    
    def _get_preset_tooltip(self, key):
        if key not in self.presets:
            return f"{key}: {tr('is empty')}\n{tr('click = save')}"
        p = self.presets[key]
        model = p.get("model", "")
        model = os.path.splitext(model)[0] if model else tr("(no model)")
        pitch = p.get("pitch", 0)
        f0 = p.get("f0_method", "?")
        idx = p.get("index_rate", 0)
        prot = p.get("protect", 0)
        filt = p.get("filter_radius", 3)
        rms = p.get("rms_mix_rate", 0.25)
        return f"{key}: {model}\nPitch: {pitch:+d}, F0: {f0}\nIndex: {idx:.2f}, {tr('Protect:')} {prot:.2f}\n{tr('Filter:')} {filt}, RMS: {rms:.2f}\n\n{tr('click = overwrite')}"
        
    def _create_widgets(self):
        progress_frame = tk.Frame(self.root, height=10)
        progress_frame.pack(side=tk.BOTTOM, fill=tk.X)
        progress_frame.pack_propagate(False)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.BOTH, expand=True)
        
        main_frame = ttk.Frame(self.root, padding="0")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        editor_frame = ttk.Frame(self.notebook, padding="0")
        convert_frame = ttk.Frame(self.notebook, padding="5")
        
        self.notebook.add(editor_frame, text=f"✂️ {tr('Editor')}")
        self.notebook.add(convert_frame, text=f"🎤 {tr('Conversion')}")
        
        self._create_editor_tab(editor_frame)
        self._create_convert_tab(convert_frame)
        
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.progress_label = ttk.Label(bottom_frame, text=tr("Ready"), anchor="w")
        self.progress_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.log_btn = ttk.Button(bottom_frame, text="📋", width=3, command=self._toggle_log)
        self.log_btn.pack(side=tk.RIGHT)
        
        self.log_frame = ttk.LabelFrame(main_frame, text=tr("Log"), padding="3")
        self.log_text = scrolledtext.ScrolledText(self.log_frame, height=4, state='disabled', 
                                                   wrap=tk.WORD, font=('Consolas', 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
    def _create_convert_tab(self, parent):
        model_frame = ttk.LabelFrame(parent, text=tr("Model"), padding="5")
        model_frame.pack(fill=tk.X, pady=(0, 5))
        model_frame.columnconfigure(1, weight=1)
        
        ttk.Label(model_frame, text=tr("Model:"), width=8).grid(row=0, column=0, sticky="w", pady=2)
        self.model_combo = ttk.Combobox(model_frame, textvariable=self.model_path, state="readonly")
        self.model_combo.grid(row=0, column=1, sticky="ew", padx=(0, 5), pady=2)
        ttk.Button(model_frame, text="🔄", width=3, command=self._scan_models).grid(row=0, column=2, pady=2)
        
        ttk.Label(model_frame, text=tr("Index:"), width=8).grid(row=1, column=0, sticky="w", pady=2)
        self.index_combo = ttk.Combobox(model_frame, textvariable=self.index_path, state="readonly")
        self.index_combo.grid(row=1, column=1, columnspan=2, sticky="ew", pady=2)
        
        file_frame = ttk.LabelFrame(parent, text=tr("Folders"), padding="5")
        file_frame.pack(fill=tk.X, pady=(0, 5))
        file_frame.columnconfigure(1, weight=1)
        
        ttk.Label(file_frame, text=tr("Input:"), width=8).grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(file_frame, textvariable=self.input_dir).grid(row=0, column=1, sticky="ew", padx=(0, 5), pady=2)
        
        btn_in = ttk.Frame(file_frame)
        btn_in.grid(row=0, column=2, pady=2)
        ttk.Button(btn_in, text="...", width=3, command=self._browse_input_dir).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(btn_in, text="📂", width=3, command=self._open_input_dir).pack(side=tk.LEFT)
        
        ttk.Label(file_frame, text=tr("Output:"), width=8).grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(file_frame, textvariable=self.output_dir).grid(row=1, column=1, sticky="ew", padx=(0, 5), pady=2)
        
        btn_out = ttk.Frame(file_frame)
        btn_out.grid(row=1, column=2, pady=2)
        ttk.Button(btn_out, text="...", width=3, command=self._browse_output_dir).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(btn_out, text="📂", width=3, command=self._open_output_dir).pack(side=tk.LEFT)
        
        self.files_info_label = ttk.Label(file_frame, text="", foreground="gray")
        self.files_info_label.grid(row=2, column=0, columnspan=3, sticky="w", pady=(2, 0))
        self._update_files_info()
        self.input_dir.trace_add("write", lambda *args: self._update_files_info())
        
        params_frame = ttk.LabelFrame(parent, text=f"{tr('Parameters')}  {tr('(2xclick on label = reset)')}", padding="8")
        params_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        f0_row = ttk.Frame(params_frame)
        f0_row.pack(fill=tk.X, pady=(0, 5))
        
        ResettableLabel(f0_row, text=tr("F0 Method:"), variable=self.f0_method, 
                        default_value=DEFAULT_SETTINGS["f0_method"],
                        on_reset=self._on_f0_reset).pack(side=tk.LEFT)
        ttk.Frame(f0_row, width=20).pack(side=tk.LEFT)
        
        self.f0_btns = {}
        for method in ["rmvpe", "mangio-crepe", "crepe"]:
            btn = ttk.Button(f0_row, text=method, width=13, command=lambda m=method: self._set_f0_method(m))
            btn.pack(side=tk.LEFT, padx=1)
            self.f0_btns[method] = btn
        
        other_methods = [m for m in F0_METHODS if m not in ["rmvpe", "mangio-crepe", "crepe"]]
        ttk.Label(f0_row, text=f"  {tr('or')} ").pack(side=tk.LEFT)
        self.f0_other_combo = ttk.Combobox(f0_row, values=other_methods, state="readonly", width=14)
        self.f0_other_combo.pack(side=tk.LEFT)
        self.f0_other_combo.bind("<<ComboboxSelected>>", self._on_f0_other_select)
        
        self._update_f0_buttons()
        self.f0_method.trace_add("write", lambda *args: self._update_f0_buttons())
        self.f0_method.trace_add("write", lambda *args: self._update_crepe_visibility())
        
        self.crepe_frame = ttk.Frame(params_frame)
        ResettableLabel(self.crepe_frame, text=tr("Analysis step:"), variable=self.crepe_hop_length,
                        default_value=DEFAULT_SETTINGS["crepe_hop_length"]).pack(side=tk.LEFT)
        ttk.Frame(self.crepe_frame, width=20).pack(side=tk.LEFT)
        ScaleWithEntry(self.crepe_frame, self.crepe_hop_length, 16, 512, step=1, 
                       entry_width=5, scale_length=150).pack(side=tk.LEFT)
        ttk.Label(self.crepe_frame, text=f"  {tr('(less = more accurate)')}", foreground="gray").pack(side=tk.LEFT)
        
        ttk.Separator(params_frame, orient='horizontal').pack(fill=tk.X, pady=8)
        
        SCALE_LEN, ENTRY_W, ROW_HEIGHT, TOP_MARGIN = 115, 5, 34, 5
        L1_LABEL, L1_BTNS, L1_SCALE = 0, 35, 150
        L2_LABEL, L2_SCALE = 380, 520
        
        container_height = TOP_MARGIN + ROW_HEIGHT * 3 + 5
        params_container = ttk.Frame(params_frame, height=container_height)
        params_container.pack(fill=tk.X, pady=(0, 5))
        params_container.pack_propagate(False)
        
        y = TOP_MARGIN
        ResettableLabel(params_container, text=tr("Pitch:"), variable=self.pitch,
                        default_value=DEFAULT_SETTINGS["pitch"]).place(x=L1_LABEL, y=y+3)
        pitch_btns = ttk.Frame(params_container)
        pitch_btns.place(x=L1_BTNS, y=y)
        for val, txt in [(-12, "-12"), (0, "0"), (12, "+12")]:
            ttk.Button(pitch_btns, text=txt, width=4, command=lambda v=val: self.pitch.set(v)).pack(side=tk.LEFT, padx=1)
        ScaleWithEntry(params_container, self.pitch, -24, 24, step=1, entry_width=ENTRY_W, scale_length=SCALE_LEN).place(x=L1_SCALE, y=y)
        
        ResettableLabel(params_container, text=tr("Pitch filter:"), variable=self.filter_radius,
                        default_value=DEFAULT_SETTINGS["filter_radius"]).place(x=L2_LABEL, y=y+3)
        ScaleWithEntry(params_container, self.filter_radius, 0, 7, step=1, entry_width=ENTRY_W, scale_length=SCALE_LEN).place(x=L2_SCALE, y=y)
        
        y = TOP_MARGIN + ROW_HEIGHT
        ResettableLabel(params_container, text=tr("Index influence:"), variable=self.index_rate,
                        default_value=DEFAULT_SETTINGS["index_rate"]).place(x=L1_LABEL, y=y+3)
        ScaleWithEntry(params_container, self.index_rate, 0, 1, step=0.01, entry_width=ENTRY_W, scale_length=SCALE_LEN).place(x=L1_SCALE, y=y)
        
        ResettableLabel(params_container, text=tr("Volume mix:"), variable=self.rms_mix_rate,
                        default_value=DEFAULT_SETTINGS["rms_mix_rate"]).place(x=L2_LABEL, y=y+3)
        ScaleWithEntry(params_container, self.rms_mix_rate, 0, 1, step=0.01, entry_width=ENTRY_W, scale_length=SCALE_LEN).place(x=L2_SCALE, y=y)
        
        y = TOP_MARGIN + ROW_HEIGHT * 2
        ResettableLabel(params_container, text=tr("Consonant protection:"), variable=self.protect,
                        default_value=DEFAULT_SETTINGS["protect"]).place(x=L1_LABEL, y=y+3)
        ScaleWithEntry(params_container, self.protect, 0, 0.5, step=0.01, entry_width=ENTRY_W, scale_length=SCALE_LEN).place(x=L1_SCALE, y=y)
        
        ResettableLabel(params_container, text=tr("Resample:"), variable=self.resample_sr,
                        default_value=DEFAULT_SETTINGS["resample_sr"]).place(x=L2_LABEL, y=y+3)
        resample_frame = ttk.Frame(params_container)
        resample_frame.place(x=L2_SCALE, y=y)
        ttk.Combobox(resample_frame, textvariable=self.resample_sr, 
                     values=[0, 16000, 22050, 32000, 44100, 48000], width=7).pack(side=tk.LEFT)
        ttk.Label(resample_frame, text=f" {tr('(0=off)')}", foreground="gray").pack(side=tk.LEFT)
        
        presets_row = ttk.Frame(params_frame)
        presets_row.pack(fill=tk.X, pady=(5, 3))
        
        reset_btn = ttk.Button(presets_row, text="↺", width=2, command=self._reset_presets)
        reset_btn.pack(side=tk.LEFT, padx=(0, 5))
        ToolTip(reset_btn, tr("Reset presets to default"))
        
        ttk.Label(presets_row, text=tr("Presets:"), foreground="#666").pack(side=tk.LEFT)
        
        for key in PRESET_KEYS:
            btn = ttk.Button(presets_row, text=key, width=4, command=lambda k=key: self._save_preset(k))
            btn.pack(side=tk.LEFT, padx=1)
            self.preset_btns[key] = btn
            ToolTip(btn, lambda k=key: self._get_preset_tooltip(k))
        
        preset_options_row = ttk.Frame(params_frame)
        preset_options_row.pack(fill=tk.X, pady=(0, 3))
        
        ttk.Label(preset_options_row, text=tr("On load (F1-F12):"), foreground="#666").pack(side=tk.LEFT)
        
        cb_model = ttk.Checkbutton(preset_options_row, text=tr("Model"), variable=self.preset_load_model)
        cb_model.pack(side=tk.LEFT, padx=(10, 0))
        ToolTip(cb_model, f"Ctrl+F1 — {tr('toggle')}\n({tr('if model empty - unchanged')})")
        
        cb_pitch = ttk.Checkbutton(preset_options_row, text=tr("Tone"), variable=self.preset_load_pitch)
        cb_pitch.pack(side=tk.LEFT, padx=(10, 0))
        ToolTip(cb_pitch, f"Ctrl+F2 — {tr('toggle')}")
        
        cb_f0 = ttk.Checkbutton(preset_options_row, text=tr("F0 method"), variable=self.preset_load_f0)
        cb_f0.pack(side=tk.LEFT, padx=(10, 0))
        ToolTip(cb_f0, f"Ctrl+F3 — {tr('toggle')}\n{tr('(includes hop_length for crepe)')}")
        
        ttk.Label(preset_options_row, text="  (Ctrl+F1/F2/F3)", 
                  foreground="gray", font=('Segoe UI', 8)).pack(side=tk.LEFT, padx=5)
        
        bottom_params = ttk.Frame(params_frame)
        bottom_params.pack(fill=tk.X, pady=(5, 0), side=tk.BOTTOM)
        
        ttk.Button(bottom_params, text="↺", width=2, command=self._reset_all_params).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(bottom_params, text=tr("Format:")).pack(side=tk.LEFT)
        for fmt in OUTPUT_FORMATS:
            ttk.Radiobutton(bottom_params, text=fmt.upper(), variable=self.output_format, value=fmt).pack(side=tk.LEFT, padx=3)
        
        self.convert_btn = ttk.Button(bottom_params, text=f"🎤 {tr('Convert')}", command=self._convert)
        self.convert_btn.pack(side=tk.RIGHT, padx=2)
        
        self._update_crepe_visibility()
        
    def _update_files_info(self):
        input_path = self._get_input_dir()
        if os.path.exists(input_path):
            files = [f for f in os.listdir(input_path) if f.lower().endswith(AUDIO_EXTENSIONS)]
            self.files_info_label.config(text=f"{tr('Audio files found:')} {len(files)}")
        else:
            self.files_info_label.config(text=tr("Folder does not exist"))
        
    def _set_f0_method(self, method):
        self.f0_method.set(method)
        self.f0_other_combo.set("")
        
    def _on_f0_other_select(self, event):
        method = self.f0_other_combo.get()
        if method:
            self.f0_method.set(method)
            
    def _on_f0_reset(self):
        self.f0_other_combo.set("")
        self._update_f0_buttons()
        self._update_crepe_visibility()
            
    def _update_f0_buttons(self):
        current = self.f0_method.get()
        for method, btn in self.f0_btns.items():
            btn.state(['pressed'] if method == current else ['!pressed'])
        self.f0_other_combo.set(current if current not in self.f0_btns else "")
            
    def _update_crepe_visibility(self):
        if self.f0_method.get() in CREPE_METHODS_WITH_HOP:
            if not self.crepe_frame.winfo_ismapped():
                children = self.crepe_frame.master.winfo_children()
                self.crepe_frame.pack(fill=tk.X, pady=(0, 3), after=children[0])
        else:
            self.crepe_frame.pack_forget()
        
    def _create_editor_tab(self, parent):
        from editor import EditorTab
        self.editor = EditorTab(
            parent, 
            self._get_converter_for_editor, 
            self.log, 
            self.set_progress,
            self._get_output_dir,
            lambda: self.saved_settings.get("editor_file", ""),
            self._set_editor_file,
            self._get_preset_info_for_editor,
            self.saved_settings.get("blend_mode", 0),
            self.saved_settings.get("crossfade_type", 0)
        )
        
    def _get_converter_for_editor(self):
        if not self._ensure_model_loaded():
            return None, {}
        return self.converter, self._get_convert_params()
        
    def _toggle_log(self):
        if self.log_visible.get():
            self.log_frame.pack_forget()
            self.log_visible.set(False)
        else:
            self.log_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
            self.log_visible.set(True)
            
    def _on_model_change(self, *args):
        model_name = self.model_path.get()
        if not model_name:
            return
        base_name = os.path.splitext(model_name)[0].lower()
        best_match, best_score = "", 0
        for index_path in self.indexes_list:
            index_lower = index_path.lower()
            if base_name in index_lower:
                score = len(base_name) + (10 if "added" in index_lower else 0)
                if score > best_score:
                    best_score, best_match = score, index_path
        if best_match:
            self.index_path.set(best_match)
            self.log(f"{tr('Index:')} {os.path.basename(best_match)}")
        
        if self.editor:
            self.editor.update_preset_display()
        
    def _scan_models(self):
        self.models_list, self.indexes_list = [], []
        if os.path.exists(WEIGHTS_DIR):
            self.models_list = [f for f in os.listdir(WEIGHTS_DIR) if f.endswith(".pth")]
        for root, dirs, files in os.walk(LOGS_DIR):
            for f in files:
                if f.endswith(".index") and "trained" not in f:
                    self.indexes_list.append(os.path.relpath(os.path.join(root, f), RVC_ROOT))
        self.model_combo['values'] = sorted(self.models_list)
        self.index_combo['values'] = ["(no index)"] + sorted(self.indexes_list)
        self.log(f"{tr('Models:')} {len(self.models_list)}, {tr('indexes:')} {len(self.indexes_list)}")
            
    def _browse_input_dir(self):
        path = filedialog.askdirectory(initialdir=self._get_input_dir())
        if path:
            self.input_dir.set(path)
            
    def _open_input_dir(self):
        path = self._get_input_dir()
        os.makedirs(path, exist_ok=True)
        os.startfile(path)
            
    def _browse_output_dir(self):
        path = filedialog.askdirectory(initialdir=self._get_output_dir())
        if path:
            self.output_dir.set(path)
            
    def _open_output_dir(self):
        path = self._get_output_dir()
        os.makedirs(path, exist_ok=True)
        os.startfile(path)
            
    def log(self, message):
        self.log_text.configure(state='normal')
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state='disabled')

    def set_progress(self, value, text=""):
        self.progress_var.set(value)
        if text:
            self.progress_label.config(text=text[:25])
        
    def _ensure_model_loaded(self):
        model_name = self.model_path.get()
        if not model_name:
            self.log(tr("Error: model not selected"))
            return False
        index_path = ""
        if self.index_path.get() and self.index_path.get() != "(no index)":
            index_path = os.path.join(RVC_ROOT, self.index_path.get())
        if self.converter is None:
            from converter import VoiceConverter
            self.converter = VoiceConverter(self.set_progress, self.log)
        if self.converter.is_model_loaded(model_name, index_path):
            return True
        self.log(f"{tr('Loading model:')} {model_name}")
        if not self.converter.initialize():
            return False
        return self.converter.load_model(os.path.join(WEIGHTS_DIR, model_name), index_path)
        
    def _get_convert_params(self):
        index_path = ""
        if self.index_path.get() and self.index_path.get() != "(no index)":
            index_path = os.path.join(RVC_ROOT, self.index_path.get())
        return {
            "model": self.model_path.get(),
            "pitch": self.pitch.get(),
            "f0_method": self.f0_method.get(),
            "index_path": index_path,
            "index_rate": self.index_rate.get(),
            "filter_radius": self.filter_radius.get(),
            "resample_sr": self.resample_sr.get(),
            "rms_mix_rate": self.rms_mix_rate.get(),
            "protect": self.protect.get(),
            "crepe_hop_length": self.crepe_hop_length.get(),
            "output_format": self.output_format.get()
        }
        
    def _convert(self):
        if not os.path.exists(self._get_input_dir()):
            messagebox.showwarning(tr("Warning"), tr("Input folder does not exist"))
            return
        if self.is_converting:
            return
            
        def thread():
            self.is_converting = True
            self.convert_btn.config(state='disabled')
            try:
                input_dir = self._get_input_dir()
                output_dir = self._get_output_dir()
                os.makedirs(output_dir, exist_ok=True)
                if not self._ensure_model_loaded():
                    messagebox.showerror(tr("Error"), tr("Failed to load model"))
                    return
                results = self.converter.convert_folder(
                    input_dir, output_dir, **self._get_convert_params()
                )
                if not results:
                    self.files_info_label.config(text=tr("No files to convert"), foreground="orange")
                    return
                ok = sum(1 for _, _, s in results if s)
                self.log(f"✓ {tr('Done:')} {ok}/{len(results)}")
                self.progress_label.config(text=f"✓ {tr('Done:')} {ok}/{len(results)}", 
                                           foreground="green" if ok == len(results) else "orange")
            except Exception as e:
                self.log(f"{tr('Error:')} {e}")
                import traceback
                self.log(traceback.format_exc())
                self.progress_label.config(text=f"{tr('Error:')} {str(e)[:30]}", foreground="red")
            finally:
                self.is_converting = False
                self.convert_btn.config(state='normal')
                self._save_current_settings()
                
        threading.Thread(target=thread, daemon=True).start()


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use('vista')
    except:
        pass
    RVCConverterGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()