# app.py

import os
from dotenv import load_dotenv

from flask import Flask, request, abort

from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)

from src.llm_api import gemini_chat
from src.history import save_history, load_history

# .envファイルから環境変数を読み込む
load_dotenv()

# Flaskアプリケーションのインスタンスを作成
app = Flask(__name__)

# 環境変数から設定を読み込む
channel_access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
channel_secret = os.getenv('LINE_CHANNEL_SECRET')
system_prompt = os.getenv('SYSTEM_PROMPT', '応答の語尾は必ず「〜のだ」とすること。')
context_time_limit_hours = int(os.getenv('CONTEXT_TIME_LIMIT_HOURS', 1))

if not all([channel_access_token, channel_secret]):
    print("Error: LINE_CHANNEL_ACCESS_TOKEN or LINE_CHANNEL_SECRET is not set.")
    exit()

# LINE Messaging APIの設定
configuration = Configuration(access_token=channel_access_token)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)
handler = WebhookHandler(channel_secret)


# '/callback' エンドポイントへのPOSTリクエストを処理
@app.route("/callback", methods=['POST'])
def callback():
    # リクエストヘッダーから署名を取得
    signature = request.headers['X-Line-Signature']

    # リクエストボディを取得
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # 署名を検証し、Webhookイベントを処理
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


# テキストメッセージイベントを処理するハンドラ
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    user_message = event.message.text

    # 1. 会話履歴を読み込む
    history = load_history(user_id, context_time_limit_hours)

    # 2. 今回のユーザーメッセージを履歴に追加
    history.append({"role": "user", "parts": [user_message]})

    try:
        # 3. Gemini APIを呼び出す
        model_response = gemini_chat(history, system_prompt)

        # 4. ユーザーに応答を送信
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=model_response)]
            )
        )

        # 5. 今回のやり取りを保存
        save_history(user_id, user_message, model_response)

    except Exception as e:
        app.logger.error(f"Error: {e}")
        # エラーが発生したことをユーザーに通知（任意）
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="エラーが発生しました。")]
            )
        )

# スクリプトが直接実行された場合にサーバーを起動
if __name__ == "__main__":
    # ポート番号は環境変数から取得するか、デフォルトで5000を使用
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
