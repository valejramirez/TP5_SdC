# UI/routers/viewer.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

from UI.dependencies import templates
from UI.services.reader import signal_reader_service
from UI.core.config import SIG_CH1, SIG_CH2

router = APIRouter()

@router.get("/", response_class=HTMLResponse)
async def get_viewer(request: Request):
    """Renderiza la página principal del visualizador."""
    return templates.TemplateResponse("viewer.html", {"request": request})

@router.get("/stream")
async def stream_events():
    """Endpoint para el flujo de datos en tiempo real (SSE)."""
    if not signal_reader_service:
        async def error_generator():
            yield 'data: {"error": "Device not available"}\n\n'
        return EventSourceResponse(error_generator())

    return EventSourceResponse(signal_reader_service.stream_data())

class ChannelSelect(BaseModel):
    channel: int

@router.post("/select_channel")
async def select_channel(payload: ChannelSelect):
    """Recibe la petición del frontend para cambiar de canal."""
    if not signal_reader_service:
        return {"status": "error", "message": "Device not available"}
        
    if payload.channel in [SIG_CH1, SIG_CH2]:
        signal_reader_service.set_channel(payload.channel)
        return {"status": "ok", "message": f"Channel set to {payload.channel}"}
    return {"status": "error", "message": "Invalid channel"}
