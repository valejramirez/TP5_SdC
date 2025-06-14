# UI/services/reader.py
import os
import asyncio
import json
import time
import platform # Delete after eeverything works
from typing import AsyncGenerator
from UI.core import config


IS_LINUX = (platform.system() == "Linux")
if IS_LINUX:
    import fcntl # Importamos fcntl SÓLO si estamos en Linux

class SignalReader:
    """
    Gestiona la interacción con /dev/signal_reader o lo simula si no existe.
    """
    def __init__(self, device_path: str):
        self.device_path = device_path
        self.fd = None
        self.is_simulation = False
        self.sim_file_path = "sig1.bin"
        self.sim_data = []
        self.sim_pos = 0

        # Entramos en simulación si NO estamos en Linux O si el device no existe
        if not IS_LINUX or not os.path.exists(self.device_path):
            if not IS_LINUX:
                print("⚠️ Not running on Linux. Forcing SIMULATION MODE.")
            else:
                print(f"⚠️ Could not find device {self.device_path}. Switching to SIMULATION MODE.")
            
            self.is_simulation = True
            self._load_simulation_data()
            return # Salimos del constructor aacá
        
        # Este código solo se ejecuta si estamos en Linux y el device existe
        try:
            self.fd = os.open(self.device_path, os.O_RDONLY | os.O_NONBLOCK)
            print(f"✅ Successfully opened real device: {self.device_path}")
        except OSError as e:
            print(f"ERROR: Could not open device {self.device_path}. Is the kernel module loaded? Error: {e}")
            # Si falla, también entramos en simulación
            self.is_simulation = True
            self._load_simulation_data()

    def _load_simulation_data(self):
        """Carga los datos del archivo .bin para la simulación."""
        try:
            with open(self.sim_file_path, "rb") as f:
                self.sim_data = list(f.read())
            if not self.sim_data:
                print(f"WARNING: Simulation file '{self.sim_file_path}' is empty. Using default sine wave.")
                # Fallback a una onda senoidal si el archivo no existe o está vacío
                import math
                self.sim_data = [int(127.5 + 127.5 * math.sin(2 * math.pi * i / 256)) for i in range(256)]
            print(f"Loaded {len(self.sim_data)} bytes for simulation from '{self.sim_file_path}'.")
        except FileNotFoundError:
            print(f"WARNING: Simulation file '{self.sim_file_path}' not found. Using default sine wave.")
            import math
            self.sim_data = [int(127.5 + 127.5 * math.sin(2 * math.pi * i / 256)) for i in range(256)]


    def set_channel(self, channel: int):
        """Ejecuta ioctl o simula el cambio de canal."""
        if self.is_simulation:
            # En simulación, cambiamos el archivo que se está leyendo
            self.sim_file_path = f"sig{channel + 1}.bin"
            self._load_simulation_data()
            self.sim_pos = 0 # Reiniciamos la posición
            print(f"SIM: Switched to channel {channel} (reading from '{self.sim_file_path}')")
            return

        # Lógica para el device real
        if self.fd is None: return
        try:
            arg = channel.to_bytes(4, byteorder='little')
            fcntl.ioctl(self.fd, config.SR_IOC_SET_CH, arg) # Usamos fcntl para ioctl, ya que de esta forma el driver cambia el canal
            print(f"HW: Switched to channel {channel}")
        except OSError as e:
            print(f"ERROR: ioctl failed. Error: {e}")
    
    def read_data_sync(self, num_bytes: int = 16) -> list[int]: # Leemos de a 16 bytes
            """Lectura síncrona, real o simulada, que maneja chunks y looping."""
            if self.is_simulation:
                if not self.sim_data: return []
                
                chunk = []
                # Construimos el chunk byte por byte para manejar el loop fácilmente
                for _ in range(num_bytes):
                    # Si llegamos al final, volvemos al principio
                    if self.sim_pos >= len(self.sim_data):
                        self.sim_pos = 0
                    
                    chunk.append(self.sim_data[self.sim_pos])
                    self.sim_pos += 1

                # Pequeña pausa para que el stream no sea abrumadoramente rápido
                time.sleep(0.05) 
                return chunk

            # Lógica para el device real 
            if self.fd is None: return []
            try:
                raw_data = os.read(self.fd, num_bytes)
                return list(raw_data)
            except OSError:
                return []

    async def stream_data(self) -> AsyncGenerator[str, None]:
        """Generador asíncrono que emite datos para SSE."""
        while True:
            try:
                # La lectura (real o simulada) es bloqueante, la ejecutamos en un hilo
                data_list = await asyncio.to_thread(self.read_data_sync, num_bytes=16) # Leemos de a 16 bytes para eficiencia
                
                if data_list:
                    yield data_list
                
                if self.is_simulation:
                    await asyncio.sleep(0.1) # Pequeña pausa en simulación

            except asyncio.CancelledError:
                print("Client disconnected, stopping stream.")
                break
            except Exception as e:
                print(f"An error occurred in the stream: {e}")
                break
    
    def close(self):
        if self.fd:
            os.close(self.fd)
            print(f"Closed device {self.device_path}")


try:
    signal_reader_service = SignalReader(config.DEVICE_PATH)
except Exception:
    signal_reader_service = None
