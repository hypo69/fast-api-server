## \file /src/fast_api/fast_api.py
# -*- coding: utf-8 -*-
#! venv/bin/python/python3.12

"""
.. module:: src.fast_api.fast_api
    :platform: Windows, Unix
    :synopsis: Fast API server

"""
import asyncio
import functools
import json
import os, sys
import threading
from types import SimpleNamespace
from typing import List, Callable, Dict, Any
from pathlib import Path
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, APIRouter
import ngrok

import header  # <-- Обязательный импорт
from header import __root__
from src import gs
from src.utils.jjson import j_loads, j_loads_ns
from src.utils.printer import pprint as print
from src.logger import logger
from dotenv import load_dotenv
import re


try:
    config: SimpleNamespace = j_loads_ns(__root__ / 'src' / 'fast_api' / 'fast_api.json')
    config.ports: list = config.ports if isinstance(config.ports, list) else [config.ports]

except Exception as ex:
    logger.critical(f"Config file not found!")
    sys.exit()

_api_server_instance = None


class FastApiServer:
    """FastAPI server with singleton implementation."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, host: str = "127.0.0.1", title: str = "FastAPI Singleton Server", **kwargs):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True

        self.app = FastAPI(lifespan=lifespan)
        self.router = APIRouter()
        self.host = host or config.host
        self.server_tasks = {}
        self.servers = {}
        self.app.include_router(self.router)

    def add_route(self, path: str, func: Callable, methods: List[str] = ["GET"], **kwargs):
        """Добавляет маршрут к FastAPI приложению."""
        self.router.add_api_route(path, func, methods=methods, **kwargs)

    def add_new_route(self, path: str, func: Callable, methods: List[str] = ["GET"], **kwargs):
        """Добавляет новый маршрут к уже работающему приложению."""
        self.add_route(path, func, methods, **kwargs)


    async def _start_server(self, port: int):
        """Запускает uvicorn сервер асинхронно."""
        config = uvicorn.Config(self.app, host=self.host, port=port, log_level="info")
        server = uvicorn.Server(config)
        try:
            await server.serve()
            logger.success(f"Server started on: {self.host}:{port}")
        except Exception as e:
            logger.error(f"Error running server on port {port}: {e}")
        finally:
            self.servers.pop(port, None)
            
    def start(self, port: int):
         """Запускает FastAPI сервер на указанном порту."""
         if port in self.servers:
           print(f"Server already running on port {port}")
           return

         task = threading.Thread(target=asyncio.run, args=(self._start_server(port),), daemon=True)
         self.server_tasks[port] = task
         self.servers[port] = task
         task.start()
         
    def stop(self, port: int):
        """Останавливает FastAPI сервер на указанном порту."""
        if port in self.servers:
            try:
                self.servers[port]._thread.join(1)
                self.servers.pop(port)
                print(f"Server on port {port} stopped.")
            except Exception as e:
                logger.error(f"Error stopping server on port {port}: {e}")
        else:
            print(f"Server on port {port} is not running or already stopped.")


    def stop_all(self):
        """Останавливает все запущенные сервера."""
        for port in list(self.servers):
            self.stop(port)

    def get_servers_status(self):
        """Возвращает статус всех серверов."""
        return {port: "Running" if task.is_alive() else "Stopped" for port, task in self.servers.items()}

    def get_app(self):
        """Возвращает FastAPI приложение"""
        return self.app


# ngrok free tier only allows one agent. So we tear down the tunnel on application termination
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan for setting up and tearing down Ngrok tunnel."""
    load_dotenv()
    logger.info("Setting up Ngrok Tunnel")
    ngrok_token = os.getenv("NGROK_AUTH_TOKEN", "")
    ngrok_edge = os.getenv("NGROK_EDGE", "edge:edghts_")
    
    if not ngrok_token:
       logger.warning("NGROK_AUTH_TOKEN not found. Ngrok will not be enabled")
       yield
       return
       
    ngrok.set_auth_token(ngrok_token)
    ngrok_tunnel = ngrok.forward(
        addr=8443,
        labels=ngrok_edge,
        proto="labeled",
    )
    yield
    logger.info("Tearing Down Ngrok Tunnel")
    ngrok.disconnect(ngrok_tunnel.id)


def start_server(port: int, host: str):
    """Starts the FastAPI server on the specified port."""
    global _api_server_instance
    if _api_server_instance is None:
      _api_server_instance = FastApiServer(host=host)
    _api_server_instance.start(port=port)


def stop_server(port: int):
    """Stops the FastAPI server on the specified port."""
    global _api_server_instance
    if _api_server_instance:
        _api_server_instance.stop(port=port)


def stop_all_servers():
    """Stops all running FastAPI servers."""
    global _api_server_instance
    if _api_server_instance:
         _api_server_instance.stop_all()


def status_servers():
    """Show server status"""
    global _api_server_instance
    if _api_server_instance:
        servers = _api_server_instance.get_servers_status()
        if servers:
            print(f"Server initialized on host {_api_server_instance.host}")
            for port, status in servers.items():
                print(f"  - Port {port}: {status}")
        else:
            print("No servers running")
    else:
        print("Server not initialized.")


def add_new_route(path:str, func:Callable, methods:List[str] = ["GET"]):
   """Добавляет новый роут к серверу"""
   global _api_server_instance
   if _api_server_instance:
        _api_server_instance.add_new_route(path=path, func=func, methods=methods)
        print(f"Route added: {path}, {methods=}")
   else:
        print("Server not initialized. Start server first")


def parse_port_range(range_str):
    """Разбирает строку с диапазоном портов."""
    if not re.match(r'^[\d-]+$', range_str):
       print(f"Invalid port range: {range_str}")
       return []
    if '-' in range_str:
        try:
            start, end = map(int, range_str.split('-'))
            if start > end:
                raise ValueError("Invalid port range")
            return list(range(start, end + 1))
        except ValueError:
            print(f"Invalid port range: {range_str}")
            return []
    else:
        try:
            return [int(range_str)]
        except ValueError:
            print(f"Invalid port: {range_str}")
            return []
        
class CommandHandler:
    """Handles commands for the FastAPI server."""

    def __init__(self):
      pass

    def start_server(self, port: int, host: str):
        start_server(port=port, host=host)
        
    def stop_server(self, port: int):
         stop_server(port=port)
    
    def stop_all_servers(self):
         stop_all_servers()

    def status_servers(self):
         status_servers()
         
    def add_new_route(self, path:str, func:Callable, methods:List[str] = ["GET"]):
      add_new_route(path=path, func=func, methods=methods)