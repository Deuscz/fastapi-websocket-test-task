
# fastapi-websocket-test-task

## Overview

FastAPI WebSocket application that supports sending real-time notifications to connected clients.  
It includes graceful shutdown handling, worker coordination for multi-process deployment, and a simple HTML interface for testing.

### File Descriptions

- **main.py**: Initializes the FastAPI app, handles WebSocket connections, broadcasts messages, and manages graceful shutdown signals (SIGINT/SIGTERM).  
- **worker_coordinator.py**: Coordinates multiple workers, writes ALIVE/DONE files, ensures all workers finish before master exits.  
- **connection_manager.py**: Tracks active WebSocket connections, broadcasts messages to all clients, handles connect/disconnect events.  

## Setup Instructions

### Prerequisites

- Python 3.12+
- Docker & Docker Compose (optional)

### Local Setup

1. **Clone the repository:**
```bash
git clone <repository-url>
cd fastapi-websocket-test-task
```

2. **Create a virtual environment (optional but recommended):**
```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Run the application:**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
# or with multiple workers
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

The server will be available at `http://localhost:8000`.

### Docker Setup

1. **Build and run using Docker Compose:**
```bash
docker compose up
```

2. **Stop the container:**
```bash
docker compose down
```

## How to Test the WebSocket Endpoint

### Testing via Web Browser

1. **Open the web interface:**
   - Navigate to `http://localhost:8000` in your browser.
   - You'll see a simple chat interface.

2. **Test real-time messaging:**
   - Open multiple browser tabs to simulate multiple clients.
   - Type a message in one tab and click "Send".
   - All connected clients receive the message in real-time.

3. **Observe connection notifications:**
   - On connect: `Client "[IP]:port" connected.`
   - On disconnect: `Client "[IP]:port" disconnected.`

### Testing using Python

```python
import asyncio
import websockets

async def test_websocket():
    async with websockets.connect("ws://localhost:8000/ws") as ws:
        await ws.send("Hello from Python!")
        while True:
            try:
                message = await ws.recv()
                print(f"Received: {message}")
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed")
                break

asyncio.run(test_websocket())
```

### Testing using Postman

- Set connection type to **WebSocket**
- URL: `ws://localhost:8000/ws`
- Click Connect
- Send messages and observe broadcasts

## Graceful Shutdown Logic

The application implements a **graceful shutdown** mechanism that ensures all connected clients are properly notified before the server terminates.

### How It Works

1. **Shutdown Initialization:**
   - Triggered on SIGINT or SIGTERM
   - Calls `graceful_shutdown()` with a timeout of 30 minutes

2. **Client Notification:**
   - Every 5 seconds, broadcasts: `"Server is shutting down, please disconnect."`
   - Clients have time to close connections gracefully

3. **Disconnect Monitoring:**
   - Monitors `active_connections`
   - If all clients disconnect before the timeout, shutdown completes immediately
   - Otherwise, shutdown proceeds after timeout

4. **Worker Coordination:**
   - Each worker writes an ALIVE file on startup
   - Writes a DONE file when shutdown completes
   - Last worker notifies the master process to exit

5. **Lifespan Management:**
   - FastAPI lifespan context manages startup/shutdown tasks
   - `startup()` broadcasts heartbeat messages: `"Server is running..."` every 10 seconds
   - On shutdown, clients receive the shutdown notification
