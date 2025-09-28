import asyncio
import json
import logging
import os
from typing import Dict, Optional, Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("chat.server")

class ClientHandler:
    def __init__(self,
                 reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter,
                 server: "ChatServer") -> None:
        self.reader: asyncio.StreamReader = reader
        self.writer: asyncio.StreamWriter = writer
        self.addr: Any = writer.get_extra_info("peername")
        self._closed: bool = False
        self.login: Optional[str] = None
        self.server: "ChatServer" = server

    async def handle(self) -> None:
        logger.info(f"Connection from {self.addr}")
        try:
            line = await self._read_line()
            if line is None:
                logger.info(f"Client {self.addr} disconnected before sending join")
                return
            json_data = self._json_load(line)
            if not json_data or json_data.get("event") != "join" or not json_data.get("login"):
                logger.warning(f"Client {self.addr} send invalid join: {line}")
                await self._send({"event": "error", "reason": "expected join"})
                return
            
            self.login = str(json_data["login"])
            logger.info(f"User {self.login} joined to {self.addr}")
            await self.server.register(self) 

            while True:
                line = await self._read_line()
                if line is None:
                    break
                msg = self._json_load(line)
                if not msg:
                    continue
                event = msg.get("event")
                if event == "message":
                    text = msg.get("text")
                    if text is None:
                        continue
                    out_msg = {"event": "message", "text": str(text), "user": self.login}
                    await self.server.broadcast(out_msg, exclude=self) 
                    logger.info(f"{self.login}: {text}")
                elif event == "leave":
                    logger.info(f"Leave requested by {self.login}")
                    break
                else:
                    logger.debug(f"Unknown event from {self.login}: {event}")
        
        except Exception as e:
            logger.exception(f"Error handling client from {self.addr}: {e}")
        finally:
            await self.close()

    async def send_json(self, obj: dict) -> None:
        if self._closed:
            return
        await self._send(obj)

    async def _send(self, obj: dict) -> None:
        try:
            data = json.dumps(obj, ensure_ascii=False) + "\n"
            self.writer.write(data.encode())
            await self.writer.drain()
        except Exception:
            logger.exception(f"Failed to send to {self.addr}")

    async def _read_line(self) -> Optional[str]:
        try:
            data = await self.reader.readline()
            if not data:
                return None
            return data.decode().rstrip("\n")
        except Exception:
            logger.exception(f"Read error from {self.addr}")
            return None
        
    def _json_load(self, line) -> Optional[dict]:
        try:
            return json.loads(line)
        except Exception:
            logger.warning(f"Invalid JSON from {self.addr}: {line}")
            return None
        
    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        if self.login:
            await self.server.unregister(self) 

        if self.writer is not None:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception as e:
                logger.debug(f"Writer already closed or failed: {e}")

        logger.info(f"Connection closed: {self.login} {self.addr}")

class ChatServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8888) -> None:
        self.host: str = host
        self.port: int = port
        self._clients: Dict[str, ClientHandler] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    async def start(self) -> None:
        server = await asyncio.start_server(self._on_connect, self.host, self.port)
        addr = ", ".join(str(sock.getsockname()) for sock in server.sockets) if server.sockets else f"{self.host}:{self.port}"
        logger.info(f"Server started on {addr}")
        async with server:
            await server.serve_forever()

    async def _on_connect(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        client = ClientHandler(reader, writer, self)
        asyncio.create_task(client.handle())

    async def register(self, client: ClientHandler) -> None:
        prev: Optional[ClientHandler] = None
        async with self._lock:
            if client.login in self._clients:
                logger.info(f"Deleting previous connection for {client.login}")
                prev = self._clients[client.login]
        if prev:
            await prev._send({"event": "error", "reason": "another client logged in with the same name"})
            await prev.close()
    
        async with self._lock:
            self._clients[client.login] = client

        await self.broadcast({"event": "join", "login": client.login}, exclude=None)

    async def unregister(self, client: ClientHandler) -> None:
        async with self._lock:
            if client.login and self._clients.get(client.login) is client:
                self._clients.pop(client.login, None)
                logger.info(f"{client.login} has been unregistered")
                
        if client.login:
            await self.broadcast({"event": "leave", "login": client.login}, exclude=None)

    async def broadcast(self, obj: dict, exclude: Optional[ClientHandler]) -> None:
        to_send: list[ClientHandler] = []
        async with self._lock:
            for login, client in list(self._clients.items()):
                if exclude is not None and client is exclude:
                    continue
                to_send.append(client) 
        coros = [client.send_json(obj) for client in to_send]
        if coros:
            await asyncio.gather(*coros, return_exceptions=True)

def get_port_from_env() -> int:
    port_str: str = os.environ.get("CHAT_PORT", os.environ.get("PORT", "8888"))
    try:
        port: int = int(port_str)
    except Exception:
        port = 8888
    return port
    
async def main() -> None:
    port = get_port_from_env()
    server = ChatServer(port=port)
    try:
        await server.start()
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Server error")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")

