#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import hashlib
import shutil

APP_DIR = os.path.dirname(os.path.abspath(__file__))
RVC_ROOT = os.path.dirname(APP_DIR)

# ВАЖНО: Устанавливаем рабочую директорию на RVC_ROOT
os.chdir(RVC_ROOT)

sys.path.insert(0, RVC_ROOT)
sys.path.insert(0, APP_DIR)

os.environ["RVC_ROOT"] = RVC_ROOT

from lang import tr


def get_file_hash(path):
    if not os.path.exists(path):
        return None
    with open(path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def ensure_mangio_crepe():
    files = [
        "infer-web.py",
        os.path.join("infer", "modules", "vc", "modules.py"),
        os.path.join("infer", "modules", "vc", "pipeline.py"),
    ]
    
    src_dir = os.path.join(APP_DIR, "mangio-crepe", "on")
    if not os.path.exists(src_dir):
        print(f"[!] {tr('mangio-crepe folder not found:')} {src_dir}")
        return False
    
    updated = []
    for rel_path in files:
        src = os.path.join(src_dir, rel_path)
        dst = os.path.join(RVC_ROOT, rel_path)
        
        if not os.path.exists(src):
            print(f"[!] {tr('File not found:')} {src}")
            continue
            
        if get_file_hash(src) != get_file_hash(dst):
            os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
            shutil.copy2(src, dst)
            updated.append(os.path.basename(rel_path))
    
    if updated:
        print(f"[+] {tr('mangio-crepe files updated:')} {', '.join(updated)}")
    return True


ensure_mangio_crepe()

from dotenv import load_dotenv
env_path = os.path.join(RVC_ROOT, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    os.environ.setdefault("weight_root", os.path.join(RVC_ROOT, "assets", "weights"))
    os.environ.setdefault("weight_uvr5_root", os.path.join(RVC_ROOT, "assets", "uvr5_weights"))
    os.environ.setdefault("index_root", os.path.join(RVC_ROOT, "logs"))
    os.environ.setdefault("outside_index_root", os.path.join(RVC_ROOT, "logs"))

import warnings
warnings.filterwarnings("ignore")


def check_dependencies():
    missing = []
    for mod in ["torch", "numpy", "soundfile", "librosa", "fairseq"]:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    try:
        import faiss
    except ImportError:
        try:
            import faiss_cpu
        except ImportError:
            missing.append("faiss-cpu")
    
    if missing:
        print(f"{tr('Missing:')} {', '.join(missing)}")
        return False
    return True


def main():
    print(tr("RVC Editor"))
    print(f"RVC: {RVC_ROOT}")
    print()
    
    if not check_dependencies():
        input(tr("Press Enter..."))
        return
    
    print(tr("Starting..."))
    
    try:
        from gui import main as gui_main
        gui_main()
    except Exception as e:
        print(f"{tr('Error:')} {e}")
        import traceback
        traceback.print_exc()
        input(tr("Press Enter..."))


if __name__ == "__main__":
    main()