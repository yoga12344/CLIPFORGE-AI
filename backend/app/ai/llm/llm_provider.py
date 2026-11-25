"""
ClipForge AI - Local LLM Provider Interface
Defines provider-independent abstraction for running quantized GGUF models locally.
"""

import asyncio
import logging
import os
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from ...core.config import settings

logger = logging.getLogger("clipforge.ai.llm.provider")


class LLMProvider(ABC):
    """Abstract interface for local language model execution."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        cancellation_token: Optional[asyncio.Event] = None
    ) -> str:
        """Execute text completion/chat inference asynchronously."""
        pass

    @abstractmethod
    def unload(self) -> None:
        """Release all model weights and process memory."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if runtime and model weights are present."""
        pass


class LlamaCppBinaryProvider(LLMProvider):
    """
    Local inference provider utilizing optimized llama.cpp standalone binaries.
    Executes in a separate process with zero Python GIL contention and frame-level kill capability.
    """

    def __init__(
        self,
        model_path: str,
        context_window: int = 4096,
        threads: int = 6
    ):
        self.model_path = Path(model_path).resolve()
        self.context_window = context_window
        self.threads = min(threads, os.cpu_count() or 4)
        self._current_process: Optional[asyncio.subprocess.Process] = None

    @classmethod
    def get_binary_path(cls) -> Optional[Path]:
        """Locate llama-cli executable."""
        custom_dir = settings.DATA_DIR / "bin" / "llama" / "llama-cli.exe"
        if custom_dir.is_file():
            return custom_dir

        # Check system PATH
        which_path = shutil_which("llama-cli")
        if which_path:
            return Path(which_path)

        return None

    def is_available(self) -> bool:
        bin_path = self.get_binary_path()
        return bin_path is not None and self.model_path.is_file()

    def unload(self) -> None:
        """Terminate any currently executing inference process."""
        if self._current_process is not None:
            pid = self._current_process.pid
            logger.info(f"Terminating llama.cpp process PID {pid}...")
            try:
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                else:
                    self._current_process.kill()
            except Exception as e:
                logger.warning(f"Error terminating process PID {pid}: {e}")
            finally:
                self._current_process = None

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.2,
        cancellation_token: Optional[asyncio.Event] = None
    ) -> str:
        bin_path = self.get_binary_path()
        if not bin_path or not bin_path.is_file():
            raise FileNotFoundError(f"llama-cli executable not found at {bin_path}")

        if not self.model_path.is_file():
            raise FileNotFoundError(f"Model file not found at {self.model_path}")

        # Assemble prompt with system prompt if provided
        formatted_prompt = prompt
        if system_prompt:
            formatted_prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"

        cmd = [
            str(bin_path),
            "-m", str(self.model_path),
            "-p", formatted_prompt,
            "-n", str(max_tokens),
            "-c", str(self.context_window),
            "-t", str(self.threads),
            "--temp", str(temperature),
            "-st",
            "--simple-io",
            "--no-warmup",
            "--no-display-prompt",
            "--log-disable"
        ]

        logger.info(f"Spawning llama-cli with model {self.model_path.name} (threads={self.threads})...")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        self._current_process = proc

        try:
            # Poll stdout while monitoring cancellation token
            stdout_data, stderr_data = await proc.communicate()

            if cancellation_token and cancellation_token.is_set():
                self.unload()
                raise asyncio.CancelledError("LLM inference cancelled by user.")

            output_text = stdout_data.decode("utf-8", errors="replace").strip()
            # Strip CLI banner and interactive echo if present
            if "> " in output_text:
                lines = output_text.splitlines()
                gen_lines = []
                found_prompt = False
                for line in lines:
                    if not found_prompt:
                        if line.startswith("> "):
                            found_prompt = True
                    else:
                        if line.startswith("[ Prompt:") or line.strip() == "Exiting...":
                            break
                        gen_lines.append(line)
                if found_prompt and gen_lines:
                    output_text = "\n".join(gen_lines).strip()

            return output_text

        except asyncio.CancelledError:
            self.unload()
            raise
        except Exception as e:
            self.unload()
            raise RuntimeError(f"llama-cli inference failed: {e}")
        finally:
            self._current_process = None


def shutil_which(pgm: str) -> Optional[str]:
    import shutil
    return shutil.which(pgm)
