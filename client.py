import asyncio
import json
import logging
import os
import sys
from functools import partial
from typing import Optional, Tuple

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("chat.client")

def get_env_host_port() -> Tuple[str, int]:
    host: str = os.environ.get("CHAT_HOST", "127.0.0.1")
    port_str: str = os.environ.get("CHAT_PORT", os.environ.get("PORT", "8888"))
    try:
        port: int = int(port_str)
    except Exception:
        port = 8888
    return host, port

class ChatClient:
    def __init__(self, host: str, port: int, login: str) -> None:
        self.host: str = host
        self.port: int = port 
        self.writer: Optional[asyncio.StreamWriter] = None
        self.reader: Optional[asyncio.StreamReader] = None
        self._closed: bool = False
        self.login: str = login

    async def _connect(self) -> None:
        try:
            self.reader, self.writer = await asyncio.open_connection(self.host, self.port)
            logger.info(f"Connected to {self.host}: {self.port}")
            await self._send({"event": "join", "login": self.login})
        except Exception:
            logger.exception(f"Failed to connect to {self.host}: {self.port}")
            raise

    async def run(self) -> None:
        if not (self.reader and self.writer):
            await self._connect()
        tasks = [asyncio.create_task(self._listen_server()), 
                 asyncio.create_task(self._listen_stdin())]
        _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass
        await self._close()

    async def _listen_server(self) -> None:
        try:
            while True:
                line = await self.reader.readline()
                if not line:
                    logger.info("Server closed connection")
                    break
                try:
                    msg = json.loads(line.decode())
                except Exception:
                    logger.warning(f"Received invalid JSON: {line}")
                    continue
                self._handle_server_message(msg)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Error while reading from server")
    
    def _handle_server_message(self, msg: dict) -> None:
        event = msg.get("event")
        if event == "join":
            print(f"[SYSTEM] {msg.get('login')} joined the chat")
        elif event == "leave":
            print(f"[SYSTEM] {msg.get('login')} left the chat")
        elif event == "message":
            user = msg.get("user")
            text = msg.get("text")
            print(f"{user}: {text}")
        elif event == "error":
            logger.error(f"Server error: {msg.get("reason")}")
        else:
            logger.debug(f"Unknown message received: {json.dumps(msg, ensure_ascii=False)}")

    async def _listen_stdin(self) -> None:
        loop = asyncio.get_running_loop()
        try:
            while True:
                text = await loop.run_in_executor(None, partial(input, "Enter the text: "))
                text = text.rstrip("\n")
                if not text:
                    continue
                if text.strip().lower() == "quit":
                    await self._send({"event": "leave", "login": self.login})
                    break
                await self._send({"event": "message", "text": text, "user": self.login})
        except asyncio.CancelledError:
            raise

    async def _send(self, obj: dict) -> None:
        try:
            data = json.dumps(obj, ensure_ascii=False) + "\n"
            self.writer.write(data.encode())
            await self.writer.drain()
        except Exception:
            logger.exception("Failed to send")

    async def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self.writer is not None:
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception as e:
                logger.debug(f"Writer already closed or failed: {e}")

        logger.info("Client closed")
    

async def main() -> None:
    host, port = get_env_host_port()
    while True:
        login = input("Enter the name as login: ")
        if login.strip():
            break
        print("Login must be not null")
    client = ChatClient(host, port, login.strip())
    try:
        await client.run()
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Client stopped with error")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
