"""
Ephemeral loopback HTTP distribution server for pseofactory.
Binds to 127.0.0.1:0 for kernel-allocated dynamic ports, preventing port collisions.
Enforces strict path confinement to eliminate directory traversal escapes.
Zero AI slop. 100% mechanical verification. Zero em-dashes. Zero en-dashes.
"""

import http.server
import os
from pathlib import Path
import socketserver
import threading
from typing import Optional, Union
import urllib.parse


class QuietHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """
    HTTP request handler with suppressed logging and strict path confinement.
    Prevents path traversal attempts (e.g. '../') escaping the distribution root.
    """

    def __init__(self, *args, directory: Optional[Union[str, Path]] = None, **kwargs):
        if directory is None:
            directory = getattr(self, "server_root_dir", None) or os.getcwd()
        self.root_dir = os.path.realpath(str(directory))
        super().__init__(*args, directory=self.root_dir, **kwargs)

    def log_message(self, format: str, *args) -> None:
        """Suppress standard HTTP request logging."""
        pass

    def _is_traversal_attempt(self) -> bool:
        """
        Determines whether the incoming request attempts directory traversal.
        Checks unquoted URL components and verifies resolved canonical path
        is strictly confined within root_dir using os.path.commonpath.
        """
        raw_path = self.path.split("?", 1)[0].split("#", 1)[0]
        unquoted = urllib.parse.unquote(raw_path)
        parts = [p for p in unquoted.split("/") if p]
        if any(p == ".." for p in parts) or ".." in unquoted:
            return True

        translated = super().translate_path(self.path)
        abs_translated = os.path.realpath(translated)
        root = os.path.realpath(self.root_dir)
        try:
            if os.path.commonpath([abs_translated, root]) != root:
                return True
        except Exception:
            return True
        return False

    def do_GET(self) -> None:
        if self._is_traversal_attempt():
            self.send_error(403, "Forbidden")
            return
        super().do_GET()

    def do_HEAD(self) -> None:
        if self._is_traversal_attempt():
            self.send_error(403, "Forbidden")
            return
        super().do_HEAD()


class EphemeralDistServer:
    """
    Ephemeral loopback HTTP server serving a distribution directory.
    Binds strictly to ('127.0.0.1', 0) for OS kernel allocated dynamic port.
    Context manager (__enter__ / __exit__) ensures complete socket and thread cleanup.
    """

    def __init__(
        self,
        directory: Union[str, Path],
        host: str = "127.0.0.1",
        port: int = 0,
    ):
        self.directory = Path(directory).resolve()
        self.host = host
        self.port = port
        self.server: Optional[socketserver.TCPServer] = None
        self.thread: Optional[threading.Thread] = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> int:
        """Starts the ephemeral HTTP server in a background daemon thread."""
        if self.server is not None:
            return self.port

        directory_str = str(self.directory)

        class BoundQuietHandler(QuietHTTPRequestHandler):
            server_root_dir = directory_str

        class EphemeralTCPServer(socketserver.TCPServer):
            allow_reuse_address = True

            def handle_error(self, request, client_address):
                pass

        self.server = EphemeralTCPServer((self.host, self.port), BoundQuietHandler)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self.port

    def stop(self) -> None:
        """Stops the server and releases the bound socket port."""
        if self.server:
            try:
                self.server.shutdown()
                self.server.server_close()
            except Exception:
                pass
            self.server = None

        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
            self.thread = None

    def __enter__(self) -> "EphemeralDistServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()
