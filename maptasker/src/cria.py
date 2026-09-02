"""_Modified cria to fix bug: find process function:
if process_name.lower() in proc.name().lower():
...changed to...
if process_name.lower() in proc.name().lower() and proc.info["cmdline"] is not None:
"""

import atexit
import subprocess
import time
from collections.abc import Generator, Iterator
from contextlib import ContextDecorator
from typing import Any

# import httpx
# import ollama
# import psutil
# from ollama._client import Client as OllamaClient
from maptasker.src.maputil3 import ensure_and_import
from maptasker.src.primitem import PrimeItems

httpx = ensure_and_import("httpx", "httpx")
if httpx is None:
    print("MapTasker Cria: httpx could not be installed.")
psutil = ensure_and_import("psutil", "psutil")
if psutil is None:
    print("MapTasker Cria: psutil could not be installed.")


DEFAULT_MODEL = "llama3.1:8b"
DEFAULT_MESSAGE_HISTORY = [{"role": "system", "content": "You are a helpful AI assistant."}]
ollama = ensure_and_import("ollama", "ollama")
if ollama is None:
    PrimeItems.error_code = 1
    PrimeItems.error_msg = "Ollama is not installed, please install ollama from 'https://ollama.com/download'"
ollama_module = ensure_and_import("ollama", "ollama._client")
OllamaClient = ollama_module.Client


class Client(OllamaClient):
    """Handle the Ollama client with additional functionality for streaming and stopping streams."""

    def chat_stream(self, messages: list[dict[str, Any]], **kwargs: Any) -> Generator[str, None, None]:
        model = self.model
        ai = ollama

        response = ""
        self.running = True

        try:
            for chunk in ai.chat(model=model, messages=messages, stream=True, **kwargs):
                if self.stop_stream:
                    if self.allow_interruption:
                        messages.append({"role": "assistant", "content": response})
                    self.running = False
                    return
                content = chunk["message"]["content"]
                response += content
                yield content
        except ollama.ResponseError as e:
            error_msg = f"Error in chat_stream: {e.error}"
            self.messages = [{"role": "assistant", "content": error_msg}]
            return

        self.running = False

        messages.append({"role": "assistant", "content": response})
        self.messages = messages

    stop_stream = False

    def stop(self) -> None:
        if self.running:
            self.stop_stream = True
        else:
            raise ValueError("No active chat stream to stop.")

    def chat(
        self,
        prompt: str | None = None,
        messages: list | None = DEFAULT_MESSAGE_HISTORY,
        stream: bool | None = True,
        **kwargs: Any,
    ) -> str | Generator[str, None, None]:
        model = self.model
        ai = ollama

        if not prompt and not messages:
            raise ValueError("You must pass in a prompt.")

        if messages == DEFAULT_MESSAGE_HISTORY:
            messages = getattr(
                self,
                "messages",
                messages,
            )

        if prompt:
            messages.append({"role": "user", "content": prompt})

        if stream:
            return self.chat_stream(messages, **kwargs)

        chunk = ai.chat(model=model, messages=messages, stream=False, **kwargs)
        response = "".join(chunk["message"]["content"])

        messages.append({"role": "assistant", "content": response})
        self.messages = messages

        return response

    def generate_stream(self, prompt: str, **kwargs: Any) -> Generator[str, None, None]:
        model = self.model

        ai = ollama

        response = ""
        self.running = True

        for chunk in ai.generate(model=model, prompt=prompt, stream=True, **kwargs):
            if self.stop_stream:
                self.running = False
                return
            content = chunk["response"]
            response += content
            yield content

        self.running = False

    def generate(self, prompt: str, stream: bool | None = True, **kwargs: Any) -> str | Generator[str, None, None]:
        model = self.model
        ai = ollama

        if stream:
            return self.generate_stream(prompt)

        chunk = ai.generate(model=model, prompt=prompt, stream=False, **kwargs)
        response = chunk["response"]

        return response

    def clear(self) -> None:
        self.messages = [{"role": "system", "content": "You are a helpful AI assistant."}]


def check_models(model: str, silence_output: bool) -> str | None:
    model_list = ollama.list().get("models", [])
    for m in model_list:
        m_name = m.get("name", "")
        if m_name == model:
            return model
        if model in m_name:
            m_without_version = next(iter(m_name.split(":")), "")
            if model == m_without_version:
                if not silence_output:
                    print(f"LLM model found, running {m_name}...")
                return m_name
            if not silence_output:
                print(f"LLM partial match found, running {m_name}...")
            return m_name
    model_match = next((True if m.get("name") == model else False for m in model_list), False)
    if model_match:
        return model

    if not silence_output:
        print(f"LLM model not found, searching '{model}'...")

    try:
        progress = ollama.pull(model, stream=True)
        print(f"LLM model {model} found, downloading... (this will probably take a while)")
        if not silence_output:
            for chunk in progress:
                print(chunk)
            print(f"'{model}' downloaded, starting processes.")
        return model
    except Exception as e:
        print(e)
        # Model not found!
        PrimeItems.error_code = 1
        PrimeItems.error_msg = f"Invalid model {model} passed. See the model library here: https://ollama.com/library"
        return None
        # raise ValueError("Invalid model passed. See the model library here: https://ollama.com/library")


def find_process(command: list[str], process_name: str = "ollama") -> Any | None:
    process = None
    for proc in psutil.process_iter(attrs=["cmdline"]):
        try:
            if process_name.lower() in proc.name().lower() and proc.info["cmdline"] is not None:
                proc_command = proc.info["cmdline"]
                if proc_command[: len(command)] != command:
                    continue
                process = psutil.Process(pid=proc.pid)
                break
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return process


class Cria(Client):
    def __init__(
        self,
        model: str | None = DEFAULT_MODEL,
        standalone: bool | None = False,
        run_subprocess: bool | None = False,
        capture_output: bool | None = False,
        allow_interruption: bool | None = True,
        silence_output: bool | None = False,
        close_on_exit: bool | None = True,
    ) -> None:
        self.run_subprocess = run_subprocess
        self.capture_output = capture_output
        self.silence_output = silence_output
        self.close_on_exit = close_on_exit
        self.allow_interruption = allow_interruption

        ollama_process = find_process(["ollama", "serve"])
        self.ollama_process = ollama_process

        if ollama_process and run_subprocess:
            self.ollama_process.kill()

        try:
            ollama.list()
        except (httpx.ConnectError, httpx.ReadError):
            ollama_process = None

        if not ollama_process:
            ollama_stdout = subprocess.PIPE if capture_output else subprocess.DEVNULL
            ollama_stderr = subprocess.PIPE if capture_output else subprocess.DEVNULL
            try:
                self.ollama_subrprocess = subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=ollama_stdout,
                    stderr=ollama_stderr,
                )
            except FileNotFoundError:
                raise FileNotFoundError(
                    "Ollama is not installed, please install ollama from 'https://ollama.com/download'",
                )
            retries = 10
            while retries:
                try:
                    ollama.list()
                    break
                except (httpx.ConnectError, httpx.ReadError):
                    time.sleep(2)
                    retries -= 1
        else:
            self.ollama_subrprocess = None

        self.model = check_models(model, silence_output)

        if not standalone:
            self.llm = find_process(["ollama", "run", self.model])

            if run_subprocess and self.llm:
                self.llm.kill()
                self.llm = None

            if not self.llm:
                self.llm = subprocess.Popen(
                    ["ollama", "run", self.model],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

        if close_on_exit and self.ollama_subrprocess:
            atexit.register(lambda: self.ollama_subrprocess.kill())

        if close_on_exit and not standalone:
            atexit.register(lambda: self.llm.kill())

    messages = DEFAULT_MESSAGE_HISTORY

    def output(self) -> Iterator[bytes]:
        ollama_subprocess = self.ollama_subrprocess
        if not ollama_subprocess:
            raise ValueError(
                "Ollama is not running as a subprocess, you must pass run_subprocess as True to capture output.",
            )
        if not self.capture_output:
            raise ValueError("You must pass in capture_ouput as True to capture output.")

        return iter(c for c in iter(lambda: ollama_subprocess.stdout.read(1), b""))

    def close(self) -> None:
        llm = self.llm
        llm.kill()


class Model(Cria, ContextDecorator):
    def __init__(
        self,
        model: str | None = DEFAULT_MODEL,
        run_attached: bool | None = False,
        run_subprocess: bool | None = False,
        allow_interruption: bool | None = True,
        capture_output: bool | None = False,
        silence_output: bool | None = False,
        close_on_exit: bool | None = True,
    ) -> None:
        super().__init__(
            model=model,
            capture_output=capture_output,
            run_subprocess=False,
            standalone=True,
            close_on_exit=close_on_exit,
        )

        self.capture_output = capture_output
        self.allow_interruption = allow_interruption
        self.silence_output = silence_output
        self.close_on_exit = close_on_exit

        self.model = check_models(model, silence_output)
        if self.model is None:
            return

        if run_attached and run_subprocess:
            msg = "You cannot run attach to an LLM and run it as a subprocess at the same time."
            raise ValueError(msg)

        if not run_attached:
            llm_stdout = subprocess.PIPE if capture_output else subprocess.DEVNULL
            llm_stderr = subprocess.PIPE if capture_output else subprocess.DEVNULL
            self.llm = subprocess.Popen(["ollama", "run", self.model], stdout=llm_stdout, stderr=llm_stderr)  # noqa: S603, S607
        else:
            self.llm = find_process(["ollama", "run", self.model])

        if self.llm and run_subprocess:
            self.llm.kill()

            llm_stdout = subprocess.PIPE if capture_output else subprocess.DEVNULL
            llm_stderr = subprocess.PIPE if capture_output else subprocess.DEVNULL
            self.llm = subprocess.Popen(["ollama", "run", self.model], stdout=llm_stdout, stderr=llm_stderr)  # noqa: S603, S607

        if close_on_exit:
            atexit.register(lambda: self.llm.kill())

    def capture_output(self) -> Iterator[str]:
        if not self.capture_output:
            msg = "You must pass in capture_ouput as True to capture output."
            raise ValueError(msg)

        return iter(lambda: self.llm.stdout.read(1), "")

    def __enter__(self) -> "Model":  # noqa: PYI034
        return self

    def __exit__(self, *exc: object) -> None:
        llm = self.llm
        llm.kill()
