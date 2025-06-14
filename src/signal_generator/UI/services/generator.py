# app/services/generator.py
import math
from typing import Dict
import numpy as np
from UI.core import config

def make_wave(kind: str, params: Dict[str, float]) -> np.ndarray:
    """
    Devuelve un ndarray uint8 con la forma de onda pedida.
    """
    t = np.arange(config.NUM_SAMPLES, dtype=np.float32)

    if kind == "lineal":
        m = params.get("m", 1)
        b = params.get("b", 0)
        y = m * (t / config.NUM_SAMPLES) + b
    elif kind == "cuadrada":
        duty = params.get("duty", 50)
        y = (t % config.NUM_SAMPLES) < (duty / 100 * config.NUM_SAMPLES)
    elif kind == "senoidal":
        y = 0.5 * (1 + np.sin(2 * math.pi * t / config.NUM_SAMPLES))
    elif kind == "cosenoidal":
        y = 0.5 * (1 + np.cos(2 * math.pi * t / config.NUM_SAMPLES))
    elif kind == "exponencial":
        k = params.get("k", 2)
        y = np.exp(np.linspace(0, math.log(k), config.NUM_SAMPLES)) - 1
        y /= y.max() if y.max() > 0 else 1
    else:
        y = np.zeros(config.NUM_SAMPLES)

    return (y * config.MAX_VAL).clip(0, config.MAX_VAL).astype(np.uint8)

def save_bin(arr: np.ndarray, path: str):
    """Guarda el ndarray en crudo."""
    arr.tofile(path)
