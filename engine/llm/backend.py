from __future__ import annotations

import logging
import secrets
import shutil
import subprocess
import time
from pathlib import Path

import httpx

from engine.config import PROJECT_ROOT, Settings


LOGGER = logging.getLogger(__name__)


class BackendError(RuntimeError):
    pass


class LlamaBackend:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.process: subprocess.Popen | None = None
        self.api_key = f"pulpo-{secrets.token_urlsafe(18)}"
        self.owns_process = False
        self._log_handle = None

    def command(self) -> list[str]:
        executable = shutil.which("llama-server")
        if not executable:
            raise BackendError(
                "llama-server was not found. Install llama.cpp with WinGet and restart Pulpo Cookie."
            )
        command = [
            executable,
            "-hf", self.settings.hf_spec,
            "-ngl", self.settings.gpu_layers,
            "-c", str(self.settings.context_size),
            "-np", "1",
            "-t", str(self.settings.generation_threads),
            "-tb", str(self.settings.prompt_threads),
            "-fa", "on",
            "-ctk", self.settings.kv_cache_type_k,
            "-ctv", self.settings.kv_cache_type_v,
            "--host", self.settings.host,
            "--port", str(self.settings.port),
            "--no-webui",
            "--no-mmproj",
            "--cors-origins", "localhost",
            "--api-key", self.api_key,
            "--reasoning", "off",
            "--reasoning-format", "deepseek",
            "--no-reasoning-preserve",
            "--log-verbosity", "2",
        ]
        if self.settings.offline_after_download:
            command.append("--offline")
        return command

    def is_healthy(self, include_auth: bool = True) -> bool:
        headers = {"Authorization": f"Bearer {self.api_key}"} if include_auth else {}
        try:
            response = httpx.get(
                f"{self.settings.base_url}/health", headers=headers, timeout=1.5
            )
            if response.status_code != 200 or response.json().get("status") != "ok":
                return False
            if include_auth:
                models = httpx.get(
                    f"{self.settings.base_url}/v1/models", headers=headers, timeout=1.5
                )
                return models.status_code == 200
            return True
        except (httpx.HTTPError, ValueError):
            return False

    def start(self) -> None:
        if self.is_healthy():
            return
        # Refuse to take over an unrelated process already bound to Pulpo's port.
        if self.is_healthy(include_auth=False):
            raise BackendError(
                f"Port {self.settings.port} already has a llama server with different credentials."
            )
        log_path = PROJECT_ROOT / "logs" / "llama-server.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_handle = log_path.open("a", encoding="utf-8")
        startup_info = None
        if hasattr(subprocess, "STARTUPINFO"):
            startup_info = subprocess.STARTUPINFO()
            startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup_info.wShowWindow = subprocess.SW_HIDE
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        LOGGER.info("Starting local llama.cpp backend for %s", self.settings.hf_spec)
        try:
            self.process = subprocess.Popen(
                self.command(),
                cwd=PROJECT_ROOT,
                stdin=subprocess.DEVNULL,
                stdout=self._log_handle,
                stderr=subprocess.STDOUT,
                startupinfo=startup_info,
                creationflags=creation_flags,
            )
        except OSError as exc:
            raise BackendError(f"Could not start llama-server: {exc}") from exc
        self.owns_process = True
        deadline = time.monotonic() + self.settings.startup_timeout_seconds
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise BackendError(
                    f"llama-server exited during startup (code {self.process.returncode}). "
                    f"See {log_path}."
                )
            if self.is_healthy():
                LOGGER.info("Local llama.cpp backend is ready")
                return
            time.sleep(0.5)
        self.stop()
        raise BackendError(f"The model did not become ready within {self.settings.startup_timeout_seconds}s.")

    def stop(self) -> None:
        if self.process and self.owns_process and self.process.poll() is None:
            LOGGER.info("Stopping local llama.cpp backend")
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process = None
        if self._log_handle:
            self._log_handle.close()
            self._log_handle = None

    @property
    def status(self) -> str:
        if self.process and self.process.poll() is not None:
            return f"stopped ({self.process.returncode})"
        return "ready" if self.is_healthy() else "offline"
