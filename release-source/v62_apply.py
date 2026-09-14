#!/usr/bin/env python3
from pathlib import Path
import runpy

impl = Path(__file__).with_name("v62_impl.py")
runpy.run_path(str(impl), run_name="__main__")
