from __future__ import annotations

## \file /src/gs.py
# -*- coding: utf-8 -*-
#! venv/bin/python/python3.12
"""
.. module:: gemini_simplechat.src.gs
    :platform: Windows, Unix
    :synopsis: Загрузка параметров программы

"""
import header
from header import __root__
from src.utils.jjson import j_loads_ns
from pathlib import Path

gs = j_loads_ns(Path( __root__, 'config.json'))