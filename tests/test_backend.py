from pathlib import Path

from engine.config import Settings
from engine.llm.backend import LlamaBackend


def test_backend_command_uses_current_reasoning_and_gpu_flags(monkeypatch) -> None:
    monkeypatch.setattr("engine.llm.backend.shutil.which", lambda _: "C:/llama-server.exe")
    command = LlamaBackend(Settings()).command()
    assert command[0] == "C:/llama-server.exe"
    assert command[command.index("--reasoning") + 1] == "off"
    assert command[command.index("--reasoning-format") + 1] == "deepseek"
    assert command[command.index("-ngl") + 1] == "99"
    assert command[command.index("-t") + 1] == "8"
    assert command[command.index("-tb") + 1] == "16"
    assert command[command.index("-fa") + 1] == "on"
    assert command[command.index("-ctk") + 1] == "q4_0"
    assert command[command.index("-ctv") + 1] == "q4_0"
    assert "--no-webui" in command
    assert "--no-mmproj" in command


def test_stop_terminates_owned_process() -> None:
    class FakeProcess:
        returncode = None
        terminated = False

        def poll(self):
            return None

        def terminate(self):
            self.terminated = True

        def wait(self, timeout):
            self.returncode = 0

    backend = LlamaBackend(Settings())
    fake = FakeProcess()
    backend.process = fake
    backend.owns_process = True
    backend.stop()
    assert fake.terminated
    assert backend.process is None
