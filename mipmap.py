import numpy as np


class AudioMipmap:
    def __init__(self, block_size=256):
        self.block_size = block_size
        self.levels = []
        self.audio_len = 0
        self.dirty = True
    
    def build(self, audio):
        if audio is None or len(audio) == 0:
            self.levels = []
            self.audio_len = 0
            self.dirty = False
            return
        
        audio = np.asarray(audio, dtype=np.float32)
        self.audio_len = len(audio)
        self.levels = []
        
        n = (len(audio) + self.block_size - 1) // self.block_size
        pad_len = n * self.block_size
        padded = np.zeros(pad_len, dtype=np.float32)
        padded[:len(audio)] = audio
        
        reshaped = padded.reshape(n, self.block_size)
        lvl_min = np.min(reshaped, axis=1)
        lvl_max = np.max(reshaped, axis=1)
        self.levels.append((lvl_min.copy(), lvl_max.copy()))
        
        while len(lvl_min) > 1:
            n2 = (len(lvl_min) + 1) // 2
            pad_len2 = n2 * 2
            if pad_len2 > len(lvl_min):
                tmp_min = np.zeros(pad_len2, dtype=np.float32)
                tmp_max = np.zeros(pad_len2, dtype=np.float32)
                tmp_min[:len(lvl_min)] = lvl_min
                tmp_max[:len(lvl_max)] = lvl_max
                tmp_min[len(lvl_min):] = lvl_min[-1]
                tmp_max[len(lvl_max):] = lvl_max[-1]
            else:
                tmp_min, tmp_max = lvl_min, lvl_max
            lvl_min = np.minimum(tmp_min[::2], tmp_min[1::2])
            lvl_max = np.maximum(tmp_max[::2], tmp_max[1::2])
            self.levels.append((lvl_min.copy(), lvl_max.copy()))
        
        self.dirty = False
    
    def invalidate(self):
        self.dirty = True
    
    def get_envelope(self, audio, offset, visible, width):
        if audio is None or width <= 0 or visible <= 0:
            return None, None
        
        if self.dirty:
            self.build(audio)
        
        spp = visible / width
        
        if spp < self.block_size:
            return self._compute_direct(audio, offset, visible, width)
        
        if not self.levels:
            return None, None
        
        lvl_idx, bs = 0, self.block_size
        while lvl_idx < len(self.levels) - 1 and bs * 2 <= spp:
            lvl_idx += 1
            bs *= 2
        
        lvl_min, lvl_max = self.levels[lvl_idx]
        lvl_len = len(lvl_min)
        
        res_min = np.zeros(width, dtype=np.float32)
        res_max = np.zeros(width, dtype=np.float32)
        
        for x in range(width):
            ps = offset + x * visible // width
            pe = offset + (x + 1) * visible // width
            bi = ps // bs
            bj = (pe + bs - 1) // bs
            
            bi = max(0, min(bi, lvl_len))
            bj = max(bi, min(bj, lvl_len))
            
            if bj > bi:
                res_min[x] = np.min(lvl_min[bi:bj])
                res_max[x] = np.max(lvl_max[bi:bj])
        
        return res_min, res_max
    
    def _compute_direct(self, audio, offset, visible, width):
        audio_len = len(audio)
        if audio_len == 0:
            return np.zeros(width, dtype=np.float32), np.zeros(width, dtype=np.float32)
        
        res_min = np.zeros(width, dtype=np.float32)
        res_max = np.zeros(width, dtype=np.float32)
        
        for x in range(width):
            ps = offset + x * visible // width
            pe = offset + (x + 1) * visible // width
            
            ps = max(0, min(ps, audio_len))
            pe = max(ps, min(pe, audio_len))
            
            if pe > ps:
                seg = audio[ps:pe]
                res_min[x] = seg.min()
                res_max[x] = seg.max()
        
        return res_min, res_max