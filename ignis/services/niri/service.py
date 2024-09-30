import json
import os
import socket
from gi.repository import GObject  # type: ignore
from typing import Any, Dict, List
from ignis.utils import Utils
from ignis.exceptions import NiriIPCNotFoundError
from ignis.base_service import BaseService
from .constants import NIRI_SOCKET_DIR

class NiriService(BaseService):
    """
    Niri IPC client.

    Properties:
        - **workspaces** (``list[dict[str, Any]]``, read-only): A list of workspaces.
        - **active_workspace** (``Dict[str, Any]``, read-only): The currently active workspace.
        - **active_window** (``Dict[str, Any]``, read-only): The currently focused window.

    Raises:
        NiriIPCNotFoundError: If Niri IPC is not found.

    **Example usage:**

    .. code-block:: python

        from ignis.service import NiriService

        niri = NiriService.get_default()

        print(niri.workspaces)
        print(niri.active_workspace)
        print(niri.active_window)

        niri.connect("notify::active-window", lambda x, y: print(niri.active_window))
    """

    def __init__(self):
        super().__init__()
        if not os.path.exists(NIRI_SOCKET_DIR): # mypy will say that this is None type even though it isn't
            raise NiriIPCNotFoundError()

        self._workspaces: List[Dict[str, Any]] = []
        self._active_workspace: Dict[str, Any] = {}
        self._active_window: Dict[str, Any] = {}

        self.socket = self.__connect()
        self.__listen_socket()
        self.__sync_workspaces()
        self.__sync_active_window()

    def __connect(self) -> socket.socket:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(NIRI_SOCKET_DIR)
        return sock

    @Utils.run_in_thread
    def __listen_socket(self):
        while True:
            try:
                data = self.socket.recv(4096)
                if data:
                    self.__handle_event(data)
                else:
                    break
            except Exception as e:
                print(f"Error while listening to socket: {e}")
                break

    def __sync_workspaces(self):
        request = {"action": "get_workspaces"}
        self.__send_request(request)

    def __sync_active_window(self):
        request = {"action": "get_active_window"}
        self.__send_request(request)

    def __send_request(self, request: dict) -> None:
        """
        Send a request to the Niri IPC and handle the response.
        """
        self.socket.sendall(json.dumps(request).encode("utf-8"))
        response = self.socket.recv(4096).decode("utf-8")
        self.__handle_response(response)

    def __handle_response(self, response: str) -> None:
        try:
            reply = json.loads(response)
            if "workspaces" in reply:
                self._workspaces = reply["workspaces"]
            if "active_workspace" in reply:
                self._active_workspace = reply["active_workspace"]
            if "active_window" in reply:
                self._active_window = reply["active_window"]
        except json.JSONDecodeError as e:
            print(f"Failed to decode JSON response: {e}")

    def __handle_event(self, data: bytes) -> None:
        try:
            event = json.loads(data.decode("utf-8"))
            if "event" in event:
                if event["event"] == "workspaces_changed":
                    self._workspaces = event["workspaces"]
                elif event["event"] == "workspace_activated":
                    self._active_workspace = event["workspace"]
        except json.JSONDecodeError as e:
            print(f"Failed to decode JSON event: {e}")

    @GObject.Property
    def workspaces(self) -> List[Dict[str, Any]]:
        return self._workspaces

    @GObject.Property
    def active_workspace(self) -> Dict[str, Any]:
        return self._active_workspace

    @GObject.Property
    def active_window(self) -> Dict[str, Any]:
        return self._active_window
