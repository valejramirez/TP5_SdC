# app/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Importa el router que creamos
from .routers import designer
from .core import config

# Crea la aplicación FastAPI
app = FastAPI(title="Signal Designer")

# Monta el directorio 'static' para servir CSS, JS, imágenes, etc.
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")

# Incluye las rutas definidas en el router del diseñador
app.include_router(designer.router)
