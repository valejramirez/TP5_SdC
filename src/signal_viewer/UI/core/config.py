# UI/core/config.py
from pathlib import Path

# --- Rutas ---
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
BASE_DIR = ROOT_DIR / "signal_viewer"
UI_DIR = BASE_DIR / "UI"
# --- Configuración ---
STATIC_DIR = UI_DIR / "static"
TEMPLATES_DIR = UI_DIR / "templates"
DEVICE_PATH = "/dev/signal_reader"

# --- Canales ---
SIG_CH1 = 0
SIG_CH2 = 1

# --- IOCTL (recreamos la macro _IOW de C) ---
# _IOW(SR_IOC_MAGIC, 0, int) -> _IOW('s', 0, int)
SR_IOC_MAGIC = ord('s')
SR_IOC_NR_SET_CH = 0
# La dirección para _IOW es 1 (Write)
# El tamaño de un int es 4 bytes
# La fórmula es: (dir << 30) | (size << 16) | (type << 8) | (nr)
SR_IOC_SET_CH = (1 << 30) | (4 << 16) | (SR_IOC_MAGIC << 8) | SR_IOC_NR_SET_CH
