# app/routers/designer.py
import subprocess
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import numpy as np
import os

from UI.core import config
from UI.services import generator
from UI.models.signal import SaveModel
from UI import dependencies

router = APIRouter()

# --- Helper para convertir strings a float ---
def _try_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return x

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    """Menú principal para elegir la forma de la Signal 1."""
    sig1_exists = os.path.exists(config.SIG1_PATH)
    return dependencies.templates.TemplateResponse("index.html", {"request": request, "sig1_exists": sig1_exists})

@router.get("/design/{channel}/{kind}", response_class=HTMLResponse)
def design_page(request: Request, channel: str, kind: str):
    """Página de diseño con parámetros y previsualización."""
    ctx = {
        "request": request,
        "channel": channel,
        "kind": kind,
        "samples": config.NUM_SAMPLES
    }
    return dependencies.templates.TemplateResponse("params.html", ctx)

@router.post("/preview")
async def preview(kind: str = Form(...), m: float = Form(1), b: float = Form(0), duty: float = Form(50), k: float = Form(2)):
    """Endpoint AJAX que devuelve los datos de la onda para previsualizar."""
    params = {"m": m, "b": b, "duty": duty, "k": k}
    arr = generator.make_wave(kind, params)
    return {"values": arr.tolist()}

@router.post("/save")
def save_wave(cfg: SaveModel):
    """Guarda la onda diseñada y determina el siguiente paso."""
    clean_params = {k: _try_float(v) for k, v in cfg.params.items() if v not in ("", None)}

    arr = generator.make_wave(cfg.kind, clean_params)

    path = config.SIG1_PATH if cfg.channel == "sig1" else config.SIG2_PATH
    generator.save_bin(arr, path)

    next_step = "sig2" if cfg.channel == "sig1" else "final"
    return {"next": next_step}

@router.get("/final", response_class=HTMLResponse)
def final_page(request: Request):
    """Página final para elegir el período de muestreo."""
    return dependencies.templates.TemplateResponse("final.html", {"request": request})

@router.post("/run")
def run_dispatcher(period: int = Form(...)):
    """Lanza el ejecutable externo y redirige al inicio."""
    cmd = ["sudo", config.EXECUTABLE, config.SIG1_PATH, config.SIG2_PATH, str(period)]
    subprocess.Popen(cmd)
    return RedirectResponse("/success", status_code=303)

@router.get("/success", response_class=HTMLResponse)
def success_page(request: Request):
    """Página que se muestra después de iniciar la ejecución."""
    return dependencies.templates.TemplateResponse("success.html", {"request": request})

@router.post("/reset")
def reset_signals():
    """
    Elimina los archivos .bin generados para empezar de cero.
    """
    # Usamos un bloque try/except para borrar de forma segura
    try:
        if os.path.exists(config.SIG1_PATH):
            os.remove(config.SIG1_PATH)
        if os.path.exists(config.SIG2_PATH):
            os.remove(config.SIG2_PATH)
    except OSError as e:
        # Opcional: Registrar el error si algo sale mal (ej: problemas de permisos)
        print(f"Error al eliminar los archivos de señal: {e}")
        
    # Redirigimos a la página principal, que ahora mostrará el Paso 1
    return RedirectResponse("/", status_code=303)
