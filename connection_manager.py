from fastapi import WebSocket


class ConnectionManager:
    """ Manages WebSocket connections and broadcasting messages. """

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """ Add a WebSocket connection to the active connections list. """
        await websocket.accept()
        self.active_connections.append(websocket)
        await self.broadcast(f'Client "{websocket.client}" connected.')

    async def disconnect(self, websocket: WebSocket):
        """ Remove a WebSocket connection from the active connections list. """
        self.active_connections.remove(websocket)
        await self.broadcast(f'Client "{websocket.client}" disconnected.')

    async def broadcast(self, message: str):
        """ Send a message to all active WebSocket connections. """
        for connection in self.active_connections:
            await connection.send_text(message)
