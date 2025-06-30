import json
import os
from datetime import datetime, timedelta, timezone

# 履歴を保存するディレクトリ
HISTORY_DIR = "history"
# タイムゾーンをJSTに設定
JST = timezone(timedelta(hours=+9), 'JST')

def save_history(user_id: str, user_message: str, model_response: str):
    """
    ユーザーID、ユーザーメッセージ、モデルの応答をJSONL形式で保存します。

    Args:
        user_id (str): ユーザーID。
        user_message (str): ユーザーからのメッセージ。
        model_response (str): モデルからの応答。
    """
    if not os.path.exists(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)

    history_file = os.path.join(HISTORY_DIR, f"{user_id}.jsonl")
    
    # 現在時刻をJSTで取得
    now = datetime.now(JST).isoformat()

    with open(history_file, "a", encoding="utf-8") as f:
        # ユーザーの発言を保存
        user_entry = {"timestamp": now, "role": "user", "content": user_message}
        f.write(json.dumps(user_entry, ensure_ascii=False) + "\n")
        
        # AIの応答を保存
        model_entry = {"timestamp": now, "role": "model", "content": model_response}
        f.write(json.dumps(model_entry, ensure_ascii=False) + "\n")


def load_history(user_id: str, hours_limit: int) -> list[dict]:
    """
    指定された時間内の会話履歴を読み込み、Gemini APIの形式に変換します。

    Args:
        user_id (str): ユーザーID。
        hours_limit (int): 何時間前までの履歴を読み込むか。

    Returns:
        list[dict]: Gemini APIの`contents`に渡す形式の会話履歴。
    """
    history_file = os.path.join(HISTORY_DIR, f"{user_id}.jsonl")
    if not os.path.exists(history_file):
        return []

    history = []
    limit_time = datetime.now(JST) - timedelta(hours=hours_limit)

    with open(history_file, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            # タイムスタンプ文字列をdatetimeオブジェクトに変換
            entry_time = datetime.fromisoformat(entry["timestamp"])
            
            if entry_time > limit_time:
                # Gemini APIの形式に変換して追加
                history.append({"role": entry["role"], "parts": [entry["content"]]})
    
    return history
