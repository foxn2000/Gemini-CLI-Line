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
import google.generativeai as genai
from google.generativeai.types import content_types

# ---------------------------------------------------------------------------
# ❶ 環境変数をロードし、API キーを取得
# ---------------------------------------------------------------------------
load_dotenv()
_API_KEY: Final[str | None] = os.getenv("GEMINI_API_KEY")
if _API_KEY is None:
    raise RuntimeError(
        "環境変数 GEMINI_API_KEY が見つかりません。.env に設定してください。"
    )
genai.configure(api_key=_API_KEY)

# ---------------------------------------------------------------------------
# ❷ シンプルなラッパー関数
# ---------------------------------------------------------------------------
def gemini_chat(
    history: list[content_types.PartType],
    system_prompt: str | None = None,
    /,
    *,
    model: str = "gemini-1.5-flash",
) -> str:
    """
    システムプロンプトと会話履歴を元に、Geminiからの応答を生成します。

    Parameters
    ----------
    history : list[dict[str, str]]
        会話履歴のリスト。
        例: [{"role": "user", "parts": ["..."]}, {"role": "model", "parts": ["..."]}]
    system_prompt : str, optional
        モデルに与えるシステムプロンプト, by default None
    model : str, default "gemini-1.5-flash"
        使用するGeminiモデルID。

    Returns
    -------
    str
        モデルからの応答テキスト。

    Raises
    ------
    google.genai.types.GoogleGenAiError
        ネットワーク、割り当て、安全性エラーなどが発生した場合。
    """
    chat_model = genai.GenerativeModel(
        model_name=model,
        system_instruction=system_prompt,
    )
    response = chat_model.generate_content(contents=history)
    return response.text
