from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.websockets import WebSocketDisconnect, WebSocket
import asyncio
import datetime
import logging
import os
import signal
import time
import tempfile
import pathlib

from worker_coordinator import WorkerCoordinator
from connection_manager import ConnectionManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


logger = logging.getLogger(__name__)

shutdown_trigger = asyncio.Event()
connection_manager = ConnectionManager()

SHUTDOWN_DIR = pathlib.Path(tempfile.gettempdir()) / "shutdown-coordination"
PID = os.getpid()
TIMEOUT = 30 * 60  # 30 minutes

coordinator = WorkerCoordinator(PID, SHUTDOWN_DIR, TIMEOUT)


async def startup():
    """ Broadcast server status every 10 seconds until shutdown is triggered. """
    logger.info("[startup] Background task started")
    try:
        coordinator.create_alive_file()
        while not shutdown_trigger.is_set():
            try:
                await connection_manager.broadcast("Server is running...")
            except Exception:
                logger.exception("[startup] broadcast failed")
            await asyncio.sleep(10)
    finally:
        logger.info("[startup] Background task stopping")


async def graceful_shutdown():
    """ Gracefully notify clients and allow time for connections to close. """
    logger.info("[shutdown] Graceful shutdown started (pid=%d)", PID)

    start_shutdown = time.time()

    try:
        while True:
            elapsed = time.time() - start_shutdown
            if len(connection_manager.active_connections) == 0:
                logger.info("[shutdown] No active connections, stopping…")
                return
            if elapsed > TIMEOUT:
                logger.info("[shutdown] Timeout reached, forcing shutdown")
                return
            await connection_manager.broadcast(
                "Server is shutting down, please disconnect.")
            logger.info(
                f"[shutdown] Active connections: {len(connection_manager.active_connections)}"
            )
            logger.info(
                f"[shutdown] Time left: {datetime.timedelta(seconds=TIMEOUT - elapsed)}"
            )

            await asyncio.sleep(5)
    finally:
        logger.info("[shutdown] Completed graceful shutdown")
        coordinator.exit_application()


def on_signal_received():
    """ Trigger graceful shutdown when SIGINT/SIGTERM arrives. """
    if not shutdown_trigger.is_set():
        logger.info("[signal] Shutdown signal received (pid=%d)", PID)
        shutdown_trigger.set()
        asyncio.create_task(graceful_shutdown())


def register_signal_handlers():
    """ Register signal handlers. """
    signal.signal(signal.SIGINT, lambda *_: on_signal_received())
    signal.signal(signal.SIGTERM, lambda *_: on_signal_received())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """ Application lifespan context manager. """
    register_signal_handlers()
    asyncio.create_task(startup())
    yield

# Main Application
app = FastAPI(lifespan=lifespan)


@app.get("/")
async def get():
    """ Serve the main HTML page for WebSocket interaction. """
    return HTMLResponse(
        """
        <!DOCTYPE html>
        <html>
            <head>
                <title>Chat</title>
            </head>
            <body>
                <h1>WebSocket Chat</h1>
                <form action="" onsubmit="sendMessage(event)">
                    <input type="text" id="messageText" autocomplete="off"/>
                    <button>Send</button>
                </form>
                <ul id='messages'>
                </ul>
                <script>
                    var ws = new WebSocket("ws://localhost:8000/ws");
                    ws.onmessage = function(event) {
                        var messages = document.getElementById('messages')
                        var message = document.createElement('li')
                        var content = document.createTextNode(event.data)
                        message.appendChild(content)
                        messages.appendChild(message)
                    };
                    function sendMessage(event) {
                        var input = document.getElementById("messageText")
                        ws.send(input.value)
                        input.value = ''
                        event.preventDefault()
                    }
                </script>
            </body>
        </html>
        """)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """ WebSocket endpoint for handling client connections and messages. """
    await connection_manager.connect(websocket)
    try:
        while not shutdown_trigger.is_set():
            text = await websocket.receive_text()
            await connection_manager.broadcast(f'Message from "{websocket.client}": {text}')
    except WebSocketDisconnect:
        await connection_manager.disconnect(websocket)
