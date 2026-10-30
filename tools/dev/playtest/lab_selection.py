
from pathlib import Path as _DevPath
import sys as _dev_sys
_DEV_ROOT = str(next(p for p in _DevPath(__file__).resolve().parents if (p / "tools").is_dir()))
_dev_sys.path.insert(0, _DEV_ROOT)
_dev_sys.path.insert(0, str(_DevPath(_DEV_ROOT) / "tools"))

# Allow both direct script execution and package imports.
import sys as _image_sys
from pathlib import Path as _ImagePath
_image_sys.path.insert(0, str(next(p for p in _ImagePath(__file__).resolve().parents if (p / 'tools').is_dir())))
import sys
from tools.image import Image
im = Image.open(sys.argv[1]).convert('RGB')
ys = [y for y in range(84, 196) if sum(im.getpixel((240, y))) > 230 and abs(im.getpixel((240, y))[0] - 82) < 20]
print(round((sum(ys) / len(ys) - 92) / 18) if ys else -1)
