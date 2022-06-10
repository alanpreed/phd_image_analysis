import argparse
from contextlib import contextmanager
import sys
import os
import pickle
import io as py_io

import logging
# Prevent cellpose logging info when installed as package
logging.disable(logging.INFO)

from cellpose import models, io

# CellPose requires a different python version, so can't be run from within the venv for this project
# Instead we run it through a subprocess, using this script which is copied to CellPose's location


# Used to suppress STDOUT output from CellPose, code taken from here:
# https://thesmithfam.org/blog/2012/10/25/temporarily-suppress-console-output-in-python/
@contextmanager
def suppress_stdout() -> None:
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        old_sterr = sys.stderr
        sys.stderr = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_sterr


parser = argparse.ArgumentParser()
parser.add_argument('filenames', type=str, nargs='+')
args = parser.parse_args()
image_filenames = args.filenames
channels = [0, 0]
imgs = [io.imread(file) for file in image_filenames]

with suppress_stdout():
    model = models.Cellpose(gpu=False, model_type='cyto')
    masks, flows, styles, diams = model.eval(imgs, diameter=25, channels=channels)

# Return pickled data over STDOUT, encoded following info here
# https://stackoverflow.com/questions/26218944/transmitting-a-pickled-object-output-between-python-scripts-through-a-subprocess
mask_str = pickle.dumps(masks, 0)
sys.stdout = py_io.TextIOWrapper(sys.stdout.detach(), encoding='latin-1')
print(mask_str.decode('latin-1'), end='', flush=True)
