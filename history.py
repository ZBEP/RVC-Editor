import os
import json
import shutil
import time
import numpy as np


class HistoryManager:
    """Менеджер истории операций для undo/redo"""
    
    def __init__(self, project_dir, sr=44100):
        self.project_dir = project_dir
        self.sr = sr
        self.trash_dir = os.path.join(project_dir, "trash")
        self.history_file = os.path.join(project_dir, "history.json")
        self.history = []
        self.position = -1
        self.max_history = 100
        
        os.makedirs(self.trash_dir, exist_ok=True)
        self._load()
    
    def _load(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.history = data.get("history", [])
                    self.position = data.get("position", -1)
                    self.position = min(self.position, len(self.history) - 1)
            except:
                self.history, self.position = [], -1
    
    def save(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump({"history": self.history, "position": self.position}, f)
        except:
            pass
    
    def push(self, op):
        """Добавить операцию в историю"""
        # Отсекаем redo-ветку
        if self.position < len(self.history) - 1:
            for old in self.history[self.position + 1:]:
                self._cleanup_op_files(old, can_restore=False)
            self.history = self.history[:self.position + 1]
        
        op["ts"] = time.time()
        self.history.append(op)
        self.position = len(self.history) - 1
        
        # Ограничение размера
        while len(self.history) > self.max_history:
            removed = self.history.pop(0)
            self._cleanup_op_files(removed, can_restore=False)
            self.position -= 1
        
        self.save()
    
    def undo(self):
        if self.position < 0:
            return None
        op = self.history[self.position]
        self.position -= 1
        self.save()
        return op
    
    def redo(self):
        if self.position >= len(self.history) - 1:
            return None
        self.position += 1
        self.save()
        return self.history[self.position]
    
    def can_undo(self):
        return self.position >= 0
    
    def can_redo(self):
        return self.position < len(self.history) - 1
    
    def move_to_trash(self, filepath):
        """Переместить файл в trash (не удалять)"""
        if not filepath or not os.path.exists(filepath):
            return None
        name = os.path.basename(filepath)
        trash_path = os.path.join(self.trash_dir, f"{int(time.time()*1000)}_{name}")
        try:
            shutil.move(filepath, trash_path)
            return trash_path
        except:
            return None
    
    def restore_from_trash(self, trash_path, dest_path):
        """Восстановить файл из trash"""
        if not trash_path or not os.path.exists(trash_path):
            return False
        try:
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.move(trash_path, dest_path)
            return True
        except:
            return False
    
    def copy_to_trash(self, filepath):
        """Скопировать файл в trash (оригинал остаётся)"""
        if not filepath or not os.path.exists(filepath):
            return None
        name = os.path.basename(filepath)
        trash_path = os.path.join(self.trash_dir, f"{int(time.time()*1000)}_{name}")
        try:
            shutil.copy2(filepath, trash_path)
            return trash_path
        except:
            return None
    
    def save_chunk(self, audio_data, name):
        """Сохранить audio chunk в trash для восстановления"""
        if audio_data is None or len(audio_data) == 0:
            return None
        import soundfile as sf
        path = os.path.join(self.trash_dir, f"{int(time.time()*1000)}_{name}.wav")
        try:
            sf.write(path, audio_data.astype(np.float32), self.sr)
            return path
        except:
            return None
    
    def load_chunk(self, path):
        """Загрузить audio chunk"""
        if not path or not os.path.exists(path):
            return None
        try:
            import soundfile as sf
            data, _ = sf.read(path)
            return data.astype(np.float32)
        except:
            return None
    
    def _cleanup_op_files(self, op, can_restore=True):
        """Удалить файлы связанные с операцией"""
        # Удаляем только если операция окончательно вне истории
        if can_restore:
            return
        
        for key in ["chunk_path", "trash_path", "trash_paths", "base_trash"]:
            val = op.get(key)
            if not val:
                continue
            paths = val if isinstance(val, list) else [val]
            for p in paths:
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except:
                        pass
    
    def clear(self):
        """Полная очистка истории"""
        for op in self.history:
            self._cleanup_op_files(op, can_restore=False)
        self.history = []
        self.position = -1
        self.save()
        
        # Очистка всего trash
        try:
            for f in os.listdir(self.trash_dir):
                fp = os.path.join(self.trash_dir, f)
                if os.path.isfile(fp):
                    os.remove(fp)
        except:
            pass
    
    def cleanup_old_trash(self, max_age_hours=24):
        """Удалить старые файлы из trash"""
        now = time.time()
        max_age = max_age_hours * 3600
        try:
            for f in os.listdir(self.trash_dir):
                fp = os.path.join(self.trash_dir, f)
                if os.path.isfile(fp):
                    age = now - os.path.getmtime(fp)
                    if age > max_age:
                        os.remove(fp)
        except:
            pass