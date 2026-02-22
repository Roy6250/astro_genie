from typing import Optional, List, Mapping, Any, Generator
import json
import requests
import httpx

from llama_index.core.llms import (
    CustomLLM,
    CompletionResponse,
    CompletionResponseGen,
    LLMMetadata,
    ChatResponse,
    ChatMessage,
)
from llama_index.core.llms.callbacks import llm_completion_callback, llm_chat_callback


class OurLLM(CustomLLM):
    context_window: int = 3900
    num_output: int = 4096  # ← Krutrim supports up to 4k+ tokens
    model_name: str = "Qwen3-32B"
    api_key: str = "4RJDkvFLTv9Y0iqOGwC1y"  # ← Replace with your REAL API key!

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(
            context_window=self.context_window,
            num_output=self.num_output,
            model_name=self.model_name,
        )

    # ────────────────────────────────────────────────────────────────
    #  1. Non-streaming synchronous completion (unchanged)
    # ────────────────────────────────────────────────────────────────
    @llm_completion_callback()
    def complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        url = "https://cloud.olakrutrim.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", self.num_output),
            "stream": False,
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            return CompletionResponse(
                text=data["choices"][0]["message"]["content"].strip()
            )
        except requests.RequestException as e:
            return CompletionResponse(text=f"Request error: {str(e)}")

    # ────────────────────────────────────────────────────────────────
    #  2. Non-streaming async completion (unchanged but improved)
    # ────────────────────────────────────────────────────────────────
    @llm_completion_callback()
    async def acomplete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
        url = "https://cloud.olakrutrim.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", self.num_output),
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return CompletionResponse(
                    text=data["choices"][0]["message"]["content"].strip()
                )
        except httpx.RequestError as e:
            return CompletionResponse(text=f"HTTP error: {str(e)}")

    # ────────────────────────────────────────────────────────────────
    #  3. REAL STREAMING completion (this is the new part!)
    # ────────────────────────────────────────────────────────────────
    # ------------------------------------------------------------------
# Synchronous streaming – robust parsing
# ------------------------------------------------------------------
    @llm_completion_callback()
    def stream_complete(
        self, prompt: str, **kwargs: Any
    ) -> CompletionResponseGen:
        url = "https://cloud.olakrutrim.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": kwargs.get("temperature", 0.7),
            "max_tokens": kwargs.get("max_tokens", self.num_output),
            "stream": True,
        }

        accumulated_text = ""

        try:
            with requests.post(
                url, headers=headers, json=payload, stream=True, timeout=180
            ) as response:
                response.raise_for_status()

                for line in response.iter_lines():
                    if not line:
                        continue
                    line = line.decode("utf-8").strip()

                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue  # skip malformed lines

                        # Safely extract delta – this is the key fix
                        choices = chunk.get("choices", [])
                        if not choices:
                            continue  # empty choices → skip (common at end or keep-alive)

                        delta_content = choices[0].get("delta", {}).get("content", "")
                        if delta_content:
                            accumulated_text += delta_content
                            yield CompletionResponse(
                                text=accumulated_text,
                                delta=delta_content
                            )

        except Exception as e:
            yield CompletionResponse(text=f"[Streaming error: {str(e)}]")

# ------------------------------------------------------------------
# Async streaming – same robust logic
# ------------------------------------------------------------------
# @llm_completion_callback()
# async def astream_complete(
#     self, prompt: str, **kwargs: Any
# ) -> CompletionResponseAsyncGen:
#     url = "https://cloud.olakrutrim.com/v1/chat/completions"
#     headers = {
#         "Authorization": f"Bearer {self.api_key}",
#         "Content-Type": "application/json",
#         "Accept": "text/event-stream",
#     }
#     payload = {
#         "model": self.model_name,
#         "messages": [{"role": "user", "content": prompt}],
#         "temperature": kwargs.get("temperature", 0.7),
#         "max_tokens": kwargs.get("max_tokens", self.num_output),
#         "stream": True,
#     }

#     accumulated_text = ""

#     try:
#         async with httpx.AsyncClient(timeout=None) as client:
#             async with client.stream("POST", url, headers=headers, json=payload) as response:
#                 response.raise_for_status()

#                 async for line in response.aiter_lines():
#                     line = line.strip().decode("utf-8") if isinstance(line, bytes) else line.strip()

#                     if not line or not line.startswith("data: "):
#                         continue

#                     data_str = line[6:].strip()
#                     if data_str == "[DONE]":
#                         break

#                     try:
#                         chunk = json.loads(data_str)
#                     except json.JSONDecodeError:
#                         continue

#                     choices = chunk.get("choices", [])
#                     if not choices:
#                         continue

#                     delta_content = choices[0].get("delta", {}).get("content", "")
#                     if delta_content:
#                         accumulated_text += delta_content
#                         yield CompletionResponse(
#                             text=accumulated_text,
#                             delta=delta_content
#                         )

#     except Exception as e:
#         yield CompletionResponse(text=f"[Async streaming error: {str(e)}]")

    # You can also add async chat / streaming chat later if needed