
# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import sys,subprocess,os
from tools.image import Image
sys.path.insert(0,'.')
from jobs import JOBS,TEMPLATE
for name,src,box,aspect,desc,edit in JOBS:
    if os.path.exists(f'gen_{name}.png'): continue
    c=Image.open(f'us/{src}.png').convert('RGB').crop(box)
    c.resize((c.width*4,c.height*4),Image.LANCZOS).save(f'crop_{name}.png')
    open(f'p_{name}.txt','w').write(TEMPLATE.format(desc=desc,edit=edit))
    r=subprocess.run([sys.executable,'gen.py',f'p_{name}.txt',f'gen_{name}.png','--ref',f'crop_{name}.png','--aspect',aspect,'--size','1K'],capture_output=True,text=True)
    print(name,r.stdout.strip(),r.stderr.strip()[-300:],flush=True)
