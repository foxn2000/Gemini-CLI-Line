# Gemini-CLI LINE Bot

このプロジェクトは、LINE Messaging APIとGoogleのGemini API、そしてGemini-CLIを連携させた、対話型のAIアシスタントボットです。
ユーザーはLINEを通じて自然言語で指示を出すことができ、ボットはGemini APIによる応答や、Gemini-CLIを介したファイル操作・コマンド実行などを行います。

## 主な機能

- **LINE Bot連携**: LINEのトーク画面を通じて、AIアシスタントと対話できます。
- **AIによる応答**: GoogleのGemini Proモデルを利用して、ユーザーのメッセージに対して自然な応答を生成します。
- **Gemini-CLI連携**: AIの判断に基づき、ローカル環境で`gemini`コマンドを実行します。これにより、ファイル作成、コード編集、その他のシステム操作をAIが自律的に行うことが可能です。
- **コマンド実行**: `!`から始まるメッセージを送信することで、任意のシェルコマンドを実行できます。（例: `!ls -l`）
- **作業ディレクトリの管理**: `!cd`コマンドにより、ユーザーごとに作業ディレクトリを変更できます。これにより、プロジェクトごとのコンテキストを維持したまま対話が可能です。
- **会話履歴の保持**: ユーザーごとに会話履歴を保存し、文脈に沿った応答を実現します。

## 仕組み

1.  ユーザーがLINEでメッセージを送信します。
2.  Flaskで構築されたWebhookサーバーがリクエストを受け取ります。
3.  メッセージが`!`で始まる場合、`src/command.py`がシェルコマンドとして実行し、結果を返信します。
4.  それ以外のメッセージの場合、`src/llm_api.py`がGemini APIに問い合わせます。
5.  AIの応答に`<gemini-cli>`タグが含まれている場合、`src/gemini.py`が`gemini`コマンドを実行し、その結果とAIからの補足メッセージを返信します。
6.  `<gemini-cli>`タグが含まれない場合は、AIの応答をそのまま返信します。
7.  すべての対話は`history/`ディレクトリに保存されます。

## セットアップ方法

### 1. 前提条件

- Python 3.9以上
- [Google AI CLI](https://github.com/google/generative-ai-cli)がインストールされ、`gemini`コマンドが利用可能であること。
- LINE Developersアカウントと、Messaging APIのチャネルが作成済みであること。

### 2. リポジトリのクローンと依存関係のインストール

```bash
git clone https://github.com/your-username/gemini-cli-line-bot.git
cd gemini-cli-line-bot
pip install -r requirements.txt
```

### 3. 環境変数の設定

`.env.example`をコピーして`.env`ファイルを作成し、以下の項目を設定してください。

```.env
# .env

# LINE Bot
LINE_CHANNEL_SECRET="YOUR_LINE_CHANNEL_SECRET"
LINE_CHANNEL_ACCESS_TOKEN="YOUR_LINE_CHANNEL_ACCESS_TOKEN"

# Gemini API
GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
```

### 4. サーバーの起動

```bash
python main.py
```

サーバーがポート5000で起動します。

### 5. Webhookの設定

ngrokなどのツールを使って、ローカルサーバーを外部に公開します。

```bash
ngrok http 5000
```

表示された`https://...ngrok-free.app`のようなURLをコピーし、末尾に`/callback`を追加したものを、LINE DevelopersコンソールのWebhook URLに設定します。

## 使い方

- **AIへの指示**: LINEのトーク画面で、やってほしいことを自然言語で話しかけてください。
  - 例：「`hello.py`というファイルを作って」
- **コマンド実行**: `!`の後に続けてコマンドを入力します。
  - 例：「`!ls -a`」
- **作業ディレクトリの変更**: `!cd`で移動したいディレクトリを指定します。
  - 例：「`!cd src`」
