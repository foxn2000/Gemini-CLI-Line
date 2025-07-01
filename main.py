import os
import re
from pathlib import Path
from typing import Final

from dotenv import load_dotenv
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

# Custom modules
from src.command import execute_command
from src.gemini import run_gemini
from src.history import save_history, load_history
from src.llm_api import gemini_chat

# ---------------------------------------------------------------------------
# 初期設定
# ---------------------------------------------------------------------------
# .envファイルをロード
load_dotenv()

# FlaskアプリとLINE Bot APIのハンドラを初期化
app = Flask(__name__)
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))
config = Configuration(access_token=os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))

# システムプロンプトの定義
SYSTEM_PROMPT: Final[str] = """
あなたはプログラミングアシスタントです。
ユーザーの指示を達成するために、必要に応じて以下の形式でGemini-CLIを呼び出してください。

## Gemini-CLIの呼び出し形式
応答の先頭に、以下の形式で実行したい内容を記述します。
<gemini-cli>
ここにGemini-CLIに渡す自然言語の指示を記述
</gemini-cli>

## 補足メッセージ
ツールを呼び出す際は、その後ろに続けて「ファイルを変更しました。」「コンポーネントを作成します。」のような、実行内容をユーザーに伝えるための補足メッセージを必ず記述してください。

## 応答例
ユーザー: 「カレントディレクトリに 'hello.py' というファイルを作成して」
あなた:
<gemini-cli>
Create a file named 'hello.py' in the current directory.
</gemini-cli>
`hello.py` を作成しますね。
"""

# ユーザーごとの作業ディレクトリを管理
WORK_DIRECTORIES: dict[str, Path] = {}

def get_default_workdir() -> Path:
    """環境変数からデフォルトの作業ディレクトリを取得する"""
    env_path = os.getenv("DEFAULT_WORKDIR")
    if env_path:
        path = Path(env_path).expanduser().resolve()
        if path.is_dir():
            return path
    # 環境変数が未設定、またはパスが無効な場合は、このファイルの親ディレクトリを返す
    return Path(__file__).parent.resolve()

# デフォルトの作業ディレクトリ
DEFAULT_WORKDIR: Final[Path] = get_default_workdir()

# ---------------------------------------------------------------------------
# LINE Webhookのハンドラ
# ---------------------------------------------------------------------------
@app.route("/callback", methods=["POST"])
def callback() -> str:
    """LINEからのWebhookリクエストを処理する"""
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# ---------------------------------------------------------------------------
# メッセージイベントの処理
# ---------------------------------------------------------------------------
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event: MessageEvent) -> None:
    """テキストメッセージを受信したときの処理"""
    user_id: str = event.source.user_id
    user_message: str = event.message.text
    reply_token: str = event.reply_token

    # ユーザーの作業ディレクトリを取得・設定
    workdir = WORK_DIRECTORIES.get(user_id, DEFAULT_WORKDIR)

    # メッセージが '!' で始まる場合はコマンドとして処理
    if user_message.startswith("!"):
        command = user_message[1:].strip()
        
        # `!cd` コマンドの特別処理
        if command.startswith("cd"):
            # `!cd` のみの場合、デフォルトの作業ディレクトリに戻す
            if command == "cd":
                WORK_DIRECTORIES[user_id] = DEFAULT_WORKDIR
                reply_text = f"作業ディレクトリがデフォルトに戻りました:\n{DEFAULT_WORKDIR}"
            # `!cd [path]` の場合
            elif command.startswith("cd "):
                new_dir_str = command[3:].strip()
                # パスのチルダを展開
                new_dir = Path(new_dir_str).expanduser()
                # 絶対パスでない場合は、現在の作業ディレクトリからの相対パスと見なす
                if not new_dir.is_absolute():
                    new_dir = workdir / new_dir
                
                if new_dir.is_dir():
                    WORK_DIRECTORIES[user_id] = new_dir.resolve()
                    reply_text = f"作業ディレクトリが次に変更されました:\n{WORK_DIRECTORIES[user_id]}"
                else:
                    reply_text = f"エラー: ディレクトリ '{new_dir}' が見つかりません。"
        # `!pwd` コマンドの処理
        elif command == "pwd":
            reply_text = f"現在の作業ディレクトリ:\n{workdir}"
        else:
            reply_text = execute_command(command, workdir)
    
    # それ以外はAIアシスタントとして応答
    else:
        history = load_history(user_id, hours_limit=12)
        ai_response = gemini_chat(history + [{"role": "user", "parts": [user_message]}], SYSTEM_PROMPT)

        # AIの応答からgemini-cliの呼び出しを抽出
        match = re.search(r"<gemini-cli>(.*?)</gemini-cli>", ai_response, re.DOTALL)

        if match:
            gemini_prompt = match.group(1).strip()
            # AIの応答から<gemini-cli>タグ部分を削除して補足メッセージを取得
            supplement_message = re.sub(r"<gemini-cli>.*?</gemini-cli>", "", ai_response, flags=re.DOTALL).strip()
            
            try:
                cli_output = run_gemini(gemini_prompt, workdir)
                reply_text = f"--- Gemini-CLI実行結果 ---\n{cli_output}"
                if supplement_message:
                    reply_text += f"\n\n--- AIからのメッセージ ---\n{supplement_message}"
            except (FileNotFoundError, RuntimeError) as e:
                reply_text = f"Gemini-CLIの実行中にエラーが発生しました:\n{e}"
        else:
            reply_text = ai_response
        
        save_history(user_id, user_message, ai_response)

    # LINEに応答を送信
    with ApiClient(config) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=[TextMessage(text=reply_text)],
            )
        )

# ---------------------------------------------------------------------------
# サーバーの起動
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(port=5000, debug=True)
