# main_runner.py
import uvicorn
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1", help="Host to run the server on")
    parser.add_argument("--port", default=8000, type=int, help="Port to run the server on")
    args = parser.parse_args()

    # Uvicorn apunta a 'app.main:app'
    # 'app.main' es el archivo /app/main.py
    # ':app' es el objeto FastAPI dentro de ese archivo
    uvicorn.run(
        "UI.main:app",
        host=args.host,
        port=args.port,
        reload=True  # El servidor se reinicia automáticamente con cada cambio
    )
