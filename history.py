import os
import json
import time


class HistoryManager:
    
    def __init__(self, project_dir, sr=44100):
        self.project_dir = project_dir
        self.sr = sr
        self.history_file = os.path.join(project_dir, "history.json")
        self.snapshots = []
        self.position = -1
        self.max_history = 5000
        self._load()
    
    def _load(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.snapshots = data.get("snapshots", [])
                    self.position = data.get("position", -1)
                    self.position = min(self.position, len(self.snapshots) - 1)
            except:
                self.snapshots, self.position = [], -1
    
    def save(self):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump({"snapshots": self.snapshots, "position": self.position}, f)
        except:
            pass
    
    def push(self, snapshot):
        if self.position < len(self.snapshots) - 1:
            self.snapshots = self.snapshots[:self.position + 1]
        
        snapshot["ts"] = time.time()
        self.snapshots.append(snapshot)
        self.position = len(self.snapshots) - 1
        
        while len(self.snapshots) > self.max_history:
            self.snapshots.pop(0)
            self.position -= 1
        
        self.save()
    
    def undo(self):
        if self.position <= 0:
            return None
        self.position -= 1
        self.save()
        return self.snapshots[self.position]
    
    def redo(self):
        if self.position >= len(self.snapshots) - 1:
            return None
        self.position += 1
        self.save()
        return self.snapshots[self.position]
    
    def can_undo(self):
        return self.position > 0
    
    def can_redo(self):
        return self.position < len(self.snapshots) - 1
    
    def clear(self):
        self.snapshots = []
        self.position = -1
        self.save()