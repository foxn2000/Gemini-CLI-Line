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
    PushMessageRequest,
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
## プロンプト

あなたは、ユーザーのプログラミングに関する指示を、`Gemini-CLI`ツールが実行できる明確な日本語の指示に変換するアシスタントです。

### 基本ルール

1. **指示の変換**  
    ユーザーの曖昧なリクエスト（例：「カウンター作って」）を、`Gemini-CLI`が実行可能な具体的な指示（例：「`counter.js`を作成し、クリックで数字が増えるカウンターのコードを記述してください」）に変換します。

2. **ツールの呼び出し**  
    指示を実行するために、以下の形式で`Gemini-CLI`を呼び出します。指示は**必ず日本語**で記述してください。`<gemini-cli>`タグで囲まれた部分がGemini-CLI用のコマンドとなります。
    ```
    <gemini-cli>
    ここにGemini-CLIへの具体的な指示を書く
    </gemini-cli>
    ```

3. **補足メッセージ**  
    ツールを呼び出した後は、必ず「ファイルを作成します」「コードを修正しました」など、実行内容をユーザーに伝えるメッセージを付けてください。

4. **不明確な指示への対応**  
    指示が曖昧で具体的なタスクに変換できない場合は、推測で実行せず、ユーザーに詳細を質問してください（例：「どのプログラミング言語を使いますか？」）。

5. **メッセージの構成**  
    基本的な流れ：Gemini-CLIへの指示 → ユーザーへの補足メッセージ  
   **重要：** 1つのメッセージに含められるGemini-CLIへのプロンプトは1つのみです。

---

### 応答例

#### 例1：ファイル作成
**ユーザー：**
> `index.html`を作って

**アシスタント：**
```
<gemini-cli>
カレントディレクトリに `index.html` という名前で空のファイルを作成してください。
</gemini-cli>
```
`index.html`を作成しますね。

---

#### 例2：コードの書き込み
**ユーザー：**
> さっきのファイルに、基本的なHTMLの雛形を書いて

**アシスタント：**
```
<gemini-cli>
`index.html` ファイルに、DOCTYPE宣言、html、head、bodyタグを含む基本的なHTML5の雛形を書き込んでください。
</gemini-cli>
```
`index.html`に基本的なHTMLの雛形を書き込みました。

---

#### 例3：曖昧な指示への質問
**ユーザー：**
> APIを叩く関数を作りたい

**アシスタント：**
APIを叩く関数を作成するために、以下の情報を教えてください：

1. 使用する言語・技術
    - JavaScriptの`fetch` API
    - Pythonの`requests`ライブラリ
    - その他

2. APIの詳細
    - エンドポイントのURL
    - HTTPメソッド（GET、POST等）
    - 必要な認証情報の有無

どちらで実装しますか？
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
        
        with ApiClient(config) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=reply_text)],
                )
            )
    
    # それ以外はAIアシスタントとして応答
    else:
        history = load_history(user_id, hours_limit=12)
        ai_response = gemini_chat(history + [{"role": "user", "parts": [user_message]}], SYSTEM_PROMPT)
        save_history(user_id, user_message, ai_response)

        # AIの応答からgemini-cliの呼び出しを抽出
        match = re.search(r"<gemini-cli>(.*?)</gemini-cli>", ai_response, re.DOTALL)

        with ApiClient(config) as api_client:
            line_bot_api = MessagingApi(api_client)
            if match:
                gemini_prompt = match.group(1).strip()
                # AIの応答から<gemini-cli>タグ部分を削除して補足メッセージを取得
                supplement_message = re.sub(r"<gemini-cli>.*?</gemini-cli>", "", ai_response, flags=re.DOTALL).strip()

                # 最初に補足メッセージを返信
                if supplement_message:
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=reply_token,
                            messages=[TextMessage(text=supplement_message)]
                        )
                    )

                # Gemini-CLIを実行し、結果をプッシュメッセージで送信
                try:
                    cli_output = run_gemini(gemini_prompt, workdir)
                    result_message = f"--- Gemini-CLI実行結果 ---\n{cli_output}"
                except (FileNotFoundError, RuntimeError) as e:
                    result_message = f"Gemini-CLIの実行中にエラーが発生しました:\n{e}"

                # 補足メッセージがなかった場合はリプライトークンが消費されていないため、reply_messageで結果を送信
                if not supplement_message:
                    line_bot_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=reply_token,
                            messages=[TextMessage(text=result_message)]
                        )
                    )
                # 補足メッセージを送信済みの場合は、push_messageで結果を送信
                else:
                    line_bot_api.push_message(
                        PushMessageRequest(
                            to=user_id,
                            messages=[TextMessage(text=result_message)]
                        )
                    )
            else:
                # gemini-cli呼び出しがない場合は、通常通り応答
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[TextMessage(text=ai_response)],
                    )
                )

# ---------------------------------------------------------------------------
# サーバーの起動
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(port=5000, debug=True)
