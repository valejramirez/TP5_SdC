# app/core/config.py
from pathlib import Path

NUM_SAMPLES = 256
MAX_VAL = 255 #Because of 8 bit ADC simulation

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
BASE_DIR = ROOT_DIR / "signal_generator"
UI_DIR = BASE_DIR / "UI"
TEMPLATES_DIR = UI_DIR / "templates"
STATIC_DIR = UI_DIR / "static"
SIG1_PATH = BASE_DIR/ "signals"/"sig1.bin"
SIG2_PATH = BASE_DIR/ "signals"/"sig2.bin"
EXECUTABLE = BASE_DIR/"gpio_dispatcher"/"./gpio_dispatcher"
