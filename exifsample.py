import sys
import pathlib
from PIL import Image


if len(sys.argv) > 1:
    path = pathlib.Path(sys.argv[1])
    for f in path.iterdir():
        img = Image.open(f)
        print(img)