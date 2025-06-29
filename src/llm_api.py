"""
Minimal helper for single-turn text ↔ text interaction with Gemini models.

Usage:
    from chat_gemini import gemini_chat
    print(gemini_chat("こんにちは。自己紹介して"))
"""

from __future__ import annotations

import os
from typing import Final

from dotenv import load_dotenv
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# ❶ 環境変数をロードし、API キーを取得
# ---------------------------------------------------------------------------
load_dotenv()
_API_KEY: Final[str | None] = os.getenv("GEMINI_API_KEY")
if _API_KEY is None:
    raise RuntimeError(
        "環境変数 GEMINI_API_KEY が見つかりません。.env に設定してください。"
    )

# ---------------------------------------------------------------------------
# ❷ クライアントを生成（SDK が HTTP コネクションを内部で再利用）
# ---------------------------------------------------------------------------
_client: Final[genai.Client] = genai.Client(api_key=_API_KEY)

# ---------------------------------------------------------------------------
# ❸ シンプルなラッパー関数
# ---------------------------------------------------------------------------
def gemini_chat(prompt: str, /, *, model: str = "gemini-2.5-flash") -> str:
    """
    Send a single prompt to Gemini and return the model's reply as plain text.

    Parameters
    ----------
    prompt : str
        User message (one turn).
    model : str, default "gemini-2.5-flash"
        Gemini model ID. Change to "gemini-2.5-pro" 等で温度設定可。

    Returns
    -------
    str
        Model reply.

    Raises
    ------
    google.genai.types.GoogleGenAiError
        On network / quota / safety errors, etc.
    """
    response = _client.models.generate_content(
        model=model,
        contents=prompt,  # 単一テキストなのでそのまま渡す
        # 例: config=types.GenerateContentConfig(max_output_tokens=1024)
    )
    # `response.text` は Google SDK が組み込みで提供
    return response.text