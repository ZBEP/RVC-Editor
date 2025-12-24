import os
import sys
import traceback

from lang import tr

APP_DIR = os.path.dirname(os.path.abspath(__file__))
RVC_ROOT = os.path.dirname(APP_DIR)

if os.getcwd() != RVC_ROOT:
    os.chdir(RVC_ROOT)

from dotenv import load_dotenv
env_path = os.path.join(RVC_ROOT, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    os.environ.setdefault("weight_root", os.path.join(RVC_ROOT, "assets", "weights"))
    os.environ.setdefault("weight_uvr5_root", os.path.join(RVC_ROOT, "assets", "uvr5_weights"))
    os.environ.setdefault("index_root", os.path.join(RVC_ROOT, "logs"))
    os.environ.setdefault("outside_index_root", os.path.join(RVC_ROOT, "logs"))
    os.environ.setdefault("rmvpe_root", os.path.join(RVC_ROOT, "assets", "rmvpe"))

import warnings
warnings.filterwarnings("ignore")

import logging
logging.getLogger("numba").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("fairseq").setLevel(logging.WARNING)
logging.getLogger("faiss").setLevel(logging.WARNING)

import torch
import numpy as np
import soundfile as sf

from config_app import AUDIO_EXTENSIONS


class VoiceConverter:
    
    def __init__(self, progress_callback=None, log_callback=None):
        self.progress_callback = progress_callback or (lambda x, y: None)
        self.log_callback = log_callback or print
        
        self.config = None
        self.vc = None
        self.current_model = None
        self.current_model_name = None
        self.current_index = None
        self.is_initialized = False
        
    def log(self, message):
        self.log_callback(str(message))
        
    def set_progress(self, value, text=""):
        self.progress_callback(value, text)
        
    def initialize(self):
        if self.is_initialized:
            return True
            
        try:
            self.log(tr("Initializing RVC..."))
            self.set_progress(10, tr("Loading configuration..."))
            
            from configs.config import Config
            self.config = Config()
            
            self.set_progress(20, tr("Loading VC module..."))
            
            from infer.modules.vc.modules import VC
            self.vc = VC(self.config)
            
            self.set_progress(30, tr("RVC initialized"))
            self.log(f"{tr('Device:')} {self.config.device}")
            self.log(f"{tr('Half precision:')} {self.config.is_half}")
            
            self.is_initialized = True
            return True
            
        except Exception as e:
            self.log(f"{tr('Initialization error:')} {str(e)}")
            self.log(traceback.format_exc())
            return False
    
    def is_model_loaded(self, model_name, index_path):
        if not self.is_initialized or self.vc is None:
            return False
        if self.current_model_name != model_name:
            return False
        if self.current_index != index_path:
            return False
        return True
            
    def load_model(self, model_path, index_path=""):
        if not self.is_initialized:
            if not self.initialize():
                return False
                
        try:
            if os.path.isabs(model_path):
                model_name = os.path.basename(model_path)
            else:
                model_name = model_path
            
            if self.is_model_loaded(model_name, index_path):
                self.log(f"{model_name} - {tr('Model already loaded')}")
                return True
                
            self.log(f"{tr('Loading model:')} {model_name}")
            self.set_progress(40, f"{tr('Loading')} {model_name}...")
            
            result = self.vc.get_vc(model_name, 0.33, 0.33)
            
            self.log(tr("Load result: model initialized"))
            
            self.current_model = model_path
            self.current_model_name = model_name
            self.current_index = index_path
            
            self.set_progress(60, tr("Model loaded"))
            self.log(tr("Model loaded successfully"))
            return True
            
        except Exception as e:
            self.log(f"{tr('Model load error:')} {str(e)}")
            self.log(traceback.format_exc())
            return False
    
    def ensure_model(self, model_name, index_path):
        if self.is_model_loaded(model_name, index_path):
            return True
        return self.load_model(model_name, index_path)
            
    def convert(self, input_path, output_path, **kwargs):
        if not self.is_initialized or self.vc is None:
            self.log(tr("Converter not initialized!"))
            return False
            
        try:
            pitch = kwargs.get("pitch", 0)
            f0_method = kwargs.get("f0_method", "rmvpe")
            index_path = kwargs.get("index_path", self.current_index or "")
            index_rate = kwargs.get("index_rate", 0.75)
            filter_radius = kwargs.get("filter_radius", 3)
            resample_sr = kwargs.get("resample_sr", 0)
            rms_mix_rate = kwargs.get("rms_mix_rate", 0.25)
            protect = kwargs.get("protect", 0.33)
            crepe_hop_length = kwargs.get("crepe_hop_length", 120)
            
            self.log(f"{tr('Converting:')} {os.path.basename(input_path)}")
            self.log(f"  pitch={pitch}, f0={f0_method}, index_rate={index_rate:.2f}, protect={protect:.2f}")
            
            result = self.vc.vc_single(
                0,                  # sid
                input_path,         # input_audio_path
                pitch,              # f0_up_key
                None,               # f0_file
                f0_method,          # f0_method
                index_path,         # file_index
                "",                 # file_index2
                index_rate,         # index_rate
                filter_radius,      # filter_radius
                resample_sr,        # resample_sr
                rms_mix_rate,       # rms_mix_rate
                protect,            # protect
                crepe_hop_length    # crepe_hop_length
            )
            
            if result is None:
                self.log(tr("Error: conversion result is empty"))
                return False
                
            info, audio_tuple = result
            
            if audio_tuple is None or audio_tuple[0] is None:
                self.log(f"{tr('Conversion error:')} {info}")
                return False
                
            sample_rate, audio_data = audio_tuple
            
            output_ext = os.path.splitext(output_path)[1].lower()
            
            if output_ext == ".mp3":
                temp_wav = output_path.replace(".mp3", "_temp.wav")
                sf.write(temp_wav, audio_data, sample_rate)
                self._convert_to_mp3(temp_wav, output_path)
                if os.path.exists(temp_wav):
                    os.remove(temp_wav)
            elif output_ext == ".flac":
                sf.write(output_path, audio_data, sample_rate, format='FLAC')
            elif output_ext == ".m4a":
                temp_wav = output_path.replace(".m4a", "_temp.wav")
                sf.write(temp_wav, audio_data, sample_rate)
                self._convert_to_m4a(temp_wav, output_path)
                if os.path.exists(temp_wav):
                    os.remove(temp_wav)
            else:
                sf.write(output_path, audio_data, sample_rate)
                
            self.log(f"  ✓ {tr('Saved:')} {os.path.basename(output_path)}")
            return True
            
        except Exception as e:
            self.log(f"{tr('Conversion error:')} {str(e)}")
            self.log(traceback.format_exc())
            return False
    
    def _get_ffmpeg_path(self):
        ffmpeg_paths = [
            os.path.join(RVC_ROOT, "ffmpeg.exe"),
            os.path.join(RVC_ROOT, "bin", "ffmpeg.exe"),
            os.path.join(RVC_ROOT, "runtime", "ffmpeg.exe"),
            "ffmpeg"
        ]
        
        for p in ffmpeg_paths:
            if p == "ffmpeg":
                return p
            if os.path.exists(p):
                return p
        return None
            
    def _convert_to_mp3(self, wav_path, mp3_path):
        try:
            import subprocess
            ffmpeg_path = self._get_ffmpeg_path()
                    
            if ffmpeg_path:
                cmd = [ffmpeg_path, "-y", "-i", wav_path, "-b:a", "320k", mp3_path]
                subprocess.run(cmd, capture_output=True, check=True)
            else:
                import shutil
                new_path = mp3_path.replace(".mp3", ".wav")
                shutil.copy(wav_path, new_path)
                self.log(tr("FFmpeg not found, saved as WAV"))
                
        except Exception as e:
            self.log(f"{tr('MP3 conversion error:')} {e}")
            import shutil
            new_path = mp3_path.replace(".mp3", ".wav")
            shutil.copy(wav_path, new_path)
            
    def _convert_to_m4a(self, wav_path, m4a_path):
        try:
            import subprocess
            ffmpeg_path = self._get_ffmpeg_path()
                    
            if ffmpeg_path:
                cmd = [ffmpeg_path, "-y", "-i", wav_path, "-c:a", "aac", "-b:a", "256k", m4a_path]
                subprocess.run(cmd, capture_output=True, check=True)
            else:
                import shutil
                new_path = m4a_path.replace(".m4a", ".wav")
                shutil.copy(wav_path, new_path)
                self.log(tr("FFmpeg not found, saved as WAV"))
                
        except Exception as e:
            self.log(f"{tr('M4A conversion error:')} {e}")
            import shutil
            new_path = m4a_path.replace(".m4a", ".wav")
            shutil.copy(wav_path, new_path)
    
    def get_audio_files(self, folder_path):
        if not os.path.exists(folder_path):
            return []
        
        files = []
        for f in os.listdir(folder_path):
            if f.lower().endswith(AUDIO_EXTENSIONS):
                files.append(os.path.join(folder_path, f))
        return sorted(files)
            
    def convert_folder(self, input_dir, output_dir, **kwargs):
        files = self.get_audio_files(input_dir)
        
        if not files:
            self.log(f"{tr('No audio files in folder:')} {input_dir}")
            return []
        
        results = []
        total = len(files)
        output_format = kwargs.get("output_format", "wav")
        
        self.log(f"{tr('Files found:')} {total}")
        
        for i, input_path in enumerate(files):
            self.set_progress(
                int(((i + 0.5) / total) * 100),
                f"{tr('File')} {i+1}/{total}"
            )
            
            filename = os.path.basename(input_path)
            name, _ = os.path.splitext(filename)
            output_path = os.path.join(output_dir, f"{name}_converted.{output_format}")
            
            success = self.convert(input_path, output_path, **kwargs)
            results.append((input_path, output_path, success))
            
        success_count = sum(1 for _, _, s in results if s)
        self.set_progress(100, f"{tr('Done:')} {success_count}/{total}")
        self.log(f"{tr('Processed:')} {success_count}/{total} {tr('successful')}")
        
        return results
    
    def convert_pack(self, input_dir, output_dir, presets, **kwargs):
        files = self.get_audio_files(input_dir)
        
        if not files:
            self.log(f"{tr('No audio files in folder:')} {input_dir}")
            return []
        
        results = []
        output_format = kwargs.get("output_format", "wav")
        
        model_name = ""
        if self.current_model_name:
            model_name = os.path.splitext(self.current_model_name)[0]
        
        pitch = kwargs.get("pitch", 0)
        
        total_operations = len(files) * len(presets)
        current_op = 0
        
        self.log(f"{tr('Files:')} {len(files)}, {tr('presets:')} {len(presets)}, {tr('total operations:')} {total_operations}")
        
        for input_path in files:
            filename = os.path.basename(input_path)
            name, _ = os.path.splitext(filename)
            
            for preset in presets:
                current_op += 1
                self.set_progress(
                    int((current_op / total_operations) * 100),
                    f"{tr('Operation')} {current_op}/{total_operations}"
                )
                
                f0_method = preset.get("f0_method", kwargs.get("f0_method", "rmvpe"))
                filter_radius = preset.get("filter_radius", kwargs.get("filter_radius", 3))
                crepe_hop = preset.get("crepe_hop_length", kwargs.get("crepe_hop_length", 120))
                
                f0_short = {"rmvpe": "RM", "mangio-crepe": "MC", "crepe": "CR"}.get(f0_method, f0_method[:2].upper())
                hop_suffix = f"_H{crepe_hop}" if "crepe" in f0_method else ""
                
                output_filename = f"{model_name} {pitch:+d} {f0_short}{hop_suffix} I{preset['index_rate']:.2f} P{preset['protect']:.2f} F{filter_radius} {name}.{output_format}"
                output_path = os.path.join(output_dir, output_filename)
                
                convert_kwargs = {**kwargs}
                convert_kwargs["index_rate"] = preset["index_rate"]
                convert_kwargs["protect"] = preset["protect"]
                convert_kwargs["f0_method"] = f0_method
                convert_kwargs["filter_radius"] = filter_radius
                convert_kwargs["crepe_hop_length"] = crepe_hop
                
                success = self.convert(input_path, output_path, **convert_kwargs)
                results.append({
                    "input": input_path,
                    "preset": preset,
                    "output_path": output_path,
                    "success": success
                })
        
        success_count = sum(1 for r in results if r["success"])
        self.set_progress(100, f"{tr('Done:')} {success_count}/{total_operations}")
        self.log(f"{tr('Multi-convert completed:')} {success_count}/{total_operations} {tr('successful')}")
        
        return results
        
    def cleanup(self):
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except:
            pass