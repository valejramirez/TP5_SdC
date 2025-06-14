# app/dependencies.py
from fastapi.templating import Jinja2Templates
from UI.core.config import TEMPLATES_DIR
# Definimos el objeto 'templates' aquí, en un lugar neutral.
# Ahora, cualquier otro módulo puede importarlo de forma segura desde aquí.
templates = Jinja2Templates(directory=TEMPLATES_DIR)
