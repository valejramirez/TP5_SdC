# app/models/signal.py
from typing import Dict, Any
from pydantic import BaseModel

class SaveModel(BaseModel):
    channel: str
    kind: str
    params: Dict[str, Any]
