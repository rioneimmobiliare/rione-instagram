"""Clean the text area (above the photo) of a Rione slide. usage: clean_top.py src dst"""
import sys, subprocess, os
import numpy as np
from PIL import Image

PAL = np.array([(249, 247, 241), (2, 40, 75), (1, 178, 196), (20, 232, 240)], np.float32)


def photo_top(a):
    H = a.shape[0]
    d = np.min(np.linalg.norm(a[:, :, None, :] - PAL[None, None], axis=3), axis=2)
    off = (d > 40).mean(1)  # fraction of non-palette pixels per row
    for y in range(350, H - 40):
        if off[y:y + 40].min() > 0.6:
            y0 = y
            # walk up through the fade, at most 50 px
            while y > y0 - 50 and off[y - 1] > 0.15:
                y -= 1
            return y
    return H


src, dst = sys.argv[1], sys.argv[2]
a = np.asarray(Image.open(src).convert('RGB')).astype(np.float32)
top = photo_top(a)
y1 = max(top - 12, 200)
here = os.path.dirname(os.path.abspath(__file__))
subprocess.run([sys.executable, '-I', f'{here}/sharpen.py', src, dst, 'cream,navy,teal,cyan', f'0,0,1080,{y1}'],
               check=True, capture_output=True)
print(os.path.basename(src), 'photo_top', top, 'clean_to', y1)
