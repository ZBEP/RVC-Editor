import tkinter as tk
from tkinter import ttk


class ScaleWithEntry(ttk.Frame):
    
    def __init__(self, parent, variable, from_, to, step=1, entry_width=5, scale_length=120):
        super().__init__(parent)
        
        self.variable = variable
        self.from_ = from_
        self.to = to
        self.step = step
        self.is_float = isinstance(step, float) or step < 1
        
        self.scale = ttk.Scale(
            self, from_=from_, to=to, variable=variable,
            orient=tk.HORIZONTAL, length=scale_length
        )
        self.scale.pack(side=tk.LEFT)
        
        self.scale.bind('<Button-1>', self._on_click)
        self.scale.bind('<B1-Motion>', self._on_drag)
        
        self.entry_var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.entry_var, width=entry_width, justify='center')
        self.entry.pack(side=tk.LEFT, padx=(5, 0))
        
        self._update_entry()
        variable.trace_add("write", lambda *args: self._update_entry())
        
        self.entry.bind('<Return>', self._on_entry_change)
        self.entry.bind('<FocusOut>', self._on_entry_change)
    
    def _calculate_value_from_x(self, x):
        scale_width = self.scale.winfo_width()
        slider_margin = 15
        effective_width = scale_width - 2 * slider_margin
        
        if effective_width <= 0:
            effective_width = scale_width
            slider_margin = 0
        
        effective_x = x - slider_margin
        ratio = max(0.0, min(1.0, effective_x / effective_width))
        value = self.from_ + (self.to - self.from_) * ratio
        
        if self.step >= 1:
            value = round(value)
        else:
            value = round(value / self.step) * self.step
            value = round(value, 2)
        
        return max(self.from_, min(self.to, value))
        
    def _on_click(self, event):
        if self.scale.winfo_width() > 1:
            self.variable.set(self._calculate_value_from_x(event.x))
        return "break"
    
    def _on_drag(self, event):
        if self.scale.winfo_width() > 1:
            self.variable.set(self._calculate_value_from_x(event.x))
        return "break"
        
    def _update_entry(self):
        val = self.variable.get()
        if self.is_float:
            self.entry_var.set(f"{val:.2f}")
        else:
            self.entry_var.set(str(int(round(val))))
            
    def _on_entry_change(self, event=None):
        try:
            val = float(self.entry_var.get())
            val = max(self.from_, min(self.to, val))
            if self.step >= 1:
                val = round(val)
            else:
                val = round(val / self.step) * self.step
                val = round(val, 2)
            self.variable.set(val)
        except ValueError:
            self._update_entry()


class ResettableLabel(ttk.Label):
    
    def __init__(self, parent, text, variable, default_value, on_reset=None, **kwargs):
        super().__init__(parent, text=text, **kwargs)
        self.variable = variable
        self.default_value = default_value
        self.on_reset = on_reset
        
        self.bind('<Double-Button-1>', self._reset)
        self.bind('<Enter>', lambda e: self.config(foreground="#0066cc"))
        self.bind('<Leave>', lambda e: self.config(foreground=""))
        self.config(cursor="hand2")
        
    def _reset(self, event=None):
        self.variable.set(self.default_value)
        self.config(foreground="#00aa00")
        self.after(200, lambda: self.config(foreground=""))
        if self.on_reset:
            self.on_reset()


class ToolTip:
    
    def __init__(self, widget, text_func):
        self.widget = widget
        self.text_func = text_func if callable(text_func) else lambda: text_func
        self.tip = None
        widget.bind('<Enter>', self._show)
        widget.bind('<Leave>', self._hide)
        
    def _show(self, event=None):
        text = self.text_func()
        if not text:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=text, background="#ffffe0", relief='solid', 
                 borderwidth=1, font=('Segoe UI', 8), justify='left').pack()
        
    def _hide(self, event=None):
        if self.tip:
            self.tip.destroy()
            self.tip = None
            
    def update_text(self, text_func):
        self.text_func = text_func if callable(text_func) else lambda: text_func