import streamlit as st
import anthropic
from anthropic.types.text_block import TextBlock
from dataclasses import dataclass
from typing import Dict, Union, List, Any
import json
import os
import re
import traceback
import bcrypt
import hmac
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from constants import DEFAULT_SYSTEM_PROMPT,GYARU_SYSTEM_PROMPT,MOM_SYSTEM_PROMPT,BOS_SYSTEM_PROMPT # システムプロンプト定数をインポート
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# セッション履歴の制限を追加
MAX_HISTORY = 50
# Anthropicクライアントをセットアップ
client = anthropic.Anthropic(api_key=st.secrets["api_key"]["anthropic"])

def generate_otp(length=6):
    """ランダムなOTP（ワンタイムパスワード）を生成する関数

    Args:
        length (int): OTPの長さ（デフォルト: 6桁）

    Returns:
        str: 生成されたOTP
    """
    # 数字のみの場合
    digits = string.digits
    otp = ''.join(random.choice(digits) for _ in range(length))

    # 英数字混合の場合
    # characters = string.ascii_letters + string.digits
    # otp = ''.join(random.choice(characters) for _ in range(length))

    return otp

def send_otp():
    """OTP送信ボタンが押された時の処理"""
    if "email" in st.session_state and st.session_state.email:
        # メールアドレスの検証
        email_found = False
        credentials = st.secrets["credentials"]

        for user_key in credentials:
            if user_key.startswith('user'):
                user = credentials[user_key]
                if hmac.compare_digest(st.session_state.email, user["email"]):
                    email_found = True
                    break

        if not email_found:
            st.error("登録されていないメールアドレスです。")
            # メールアドレスフォームをクリアするフラグを設定
            st.session_state.clear_email = True
            return False

        # OTP生成と有効期限設定
        otp = generate_otp()
        st.session_state["otp"] = otp
        st.session_state["otp_expiry"] = datetime.now() + timedelta(minutes=5)

        # メール送信処理
        if send_otp_email(st.session_state.email, otp):
            # メール送信成功時はクリアフラグを解除
            st.session_state.clear_email = False
            return True
        else:
            # メール送信失敗時はクリアフラグを設定
            st.session_state.clear_email = True
            return False
    else:
        st.error("メールアドレスを入力してください。")
        return False



def credentials_entered():
    """認証情報が入力された時の処理"""
    if not all(key in st.session_state for key in ["username", "password", "email", "entered_otp"]):
        st.error("全ての情報を入力してください。")
        return False

    try:
        # 認証確認
        credentials_correct = False

        # st.secretsから全ユーザー情報を取得
        credentials = st.secrets["credentials"]

        # user1, user2, user3...と順番に確認
        for user_key in credentials:
            if user_key.startswith('user'):  # userで始まるキーのみを処理
                user = credentials[user_key]
                if (hmac.compare_digest(st.session_state["username"], user["username"]) and
                    hmac.compare_digest(st.session_state["password"], user["password"]) and
                    hmac.compare_digest(st.session_state["email"], user["email"])):
                    credentials_correct = True
                    # 認証成功したユーザー情報を保存（必要な場合）
                    st.session_state["current_user"] = user_key
                    break
    except Exception as e:
        st.error(f"認証処理中にエラーが発生しました: {str(e)}")
        return False

    # OTPの確認
    otp_correct = False
    if "otp_expiry" in st.session_state and datetime.now() <= st.session_state.get("otp_expiry"):
        otp_correct = (st.session_state.get("otp") == st.session_state.get("entered_otp"))
    else:
        st.error("認証コードの有効期限が切れているか、認証コードが送信されていません。")
        return False

    # 全ての認証が成功した場合
    if credentials_correct and otp_correct:
        st.session_state["authentication_status"] = True
        # 機密情報の削除
        for key in ["password", "entered_otp", "otp"]:
            if key in st.session_state:
                del st.session_state[key]
        return True
    else:
        st.session_state["authentication_status"] = False
        if not credentials_correct:
            st.error("ユーザー名、パスワード、またはメールアドレスが正しくありません。")
        elif not otp_correct:
            st.error("認証コードが正しくありません。")
        return False

def send_otp_email(email, otp):
    """OTPをメールで送信する関数"""
    # メール送信の設定
    smtp_server = st.secrets["email"]["smtp_server"]
    smtp_port = st.secrets["email"]["smtp_port"]
    sender_email = st.secrets["email"]["sender_email"]
    sender_password = st.secrets["email"]["sender_password"]

    # メールの作成
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = email
    message["Subject"] = "ひらたに🐈️ま謹製、生成AIと遊ぶWebAppの認証コード"

    body = f"""
    以下認証コードです。認証コードの項目に入力してね：

    {otp}

    ※このコードは5分間有効です。
    """

    message.attach(MIMEText(body, "plain"))

    try:
        # SMTPサーバーへの接続と送信
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(message)
        return True
    except Exception as e:
        st.error(f"メール送信エラー: {str(e)}")
        return False

def generate_otp():
    """6桁のOTPを生成する関数"""
    return str(random.randint(100000, 999999))

def check_password():
    """パスワードとメールOTPチェックを行う関数"""
    # 最初に初期化
    if "stored_username" not in st.session_state:  # ← キー名を変更！
        st.session_state.stored_username = ""

    # ログイン状態のチェック
    if "authentication_status" in st.session_state and st.session_state["authentication_status"]:
        return True

    # UI部分
    placeholder = st.empty()

    # 認証コード送信前のフォーム
    with placeholder.form("initial_login"):
        st.markdown("### ログイン")
        st.text_input("ユーザー名", key="username")
        st.text_input("パスワード", type="password", key="password")

        # メールアドレス入力欄の値を維持するかクリアするかの制御
        email_value = st.session_state.get("email", "") if not st.session_state.get("clear_email", False) else ""
        st.text_input("メールアドレス", key="email", value=email_value)

        # メール送信ボタン
        send_otp_button = st.form_submit_button("認証コード送信")
        st.text_input("認証コード", key="entered_otp")
        submit_button = st.form_submit_button("ログイン")

        if send_otp_button:
            if send_otp():
                st.success("認証コードを送信しました。メールをご確認ください。")
            else:
                st.error("認証コードの送信に失敗しました。")
                # メールアドレスフォームをクリアするフラグを設定
                st.session_state.clear_email = True
            return False

        if submit_button:
            if credentials_entered():
                st.session_state.stored_username = st.session_state.username  # text_inputの値を別のキーで保存
                placeholder.empty()  # 認証成功時のみフォームを消去
                return True
            else:
                # 認証失敗時の処理
                st.error("認証に失敗しました。入力内容を確認してください。")
                # メールアドレスフォームをクリアするフラグを設定
                st.session_state.clear_email = True
                return False

    return False

def get_response(user_input):
    # 過去の会話履歴を適切な形式に変換
    conversation_history = []
    for msg in st.session_state.messages:
        role = "user" if msg["role"] == "user" else "assistant"
        conversation_history.append({
            "role": role,
            "content": msg["content"]
        })

    # 新しい入力を追加
    conversation_history.append({
        "role": "user",
        "content": user_input
    })

    message = client.messages.create(
        model="claude-3-7-sonnet-20250219",
        max_tokens=5140,
        system=st.session_state.system_prompt,
        messages=conversation_history  # 会話履歴を含める
    )
    return message.content

@dataclass
class TextBlock:
    text: str
    type: str

class ChatHistoryManager:
    def __init__(self, username: str):
        self.username = username
        self.base_dir = "chat_histories"
        self.user_dir = f"{self.base_dir}/{username}"
        os.makedirs(self.user_dir, exist_ok=True)

    def save_chat(self, chat_id: str, messages: List[Dict], title: str = None):
        """チャット履歴を保存"""
        if not title:
            # 最初の会話から自動でタイトルを生成
            first_message = next((m for m in messages if m["role"] == "user"), None)
            title = first_message["content"][:20] + "..." if first_message else "無題の会話"

        chat_data = {
            "title": title,
            "timestamp": datetime.now().isoformat(),
            "messages": messages
        }

        file_path = f"{self.user_dir}/{chat_id}.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(chat_data, f, ensure_ascii=False)

    def load_chat(self, chat_id: str) -> Dict:
        try:
            file_path = f"{self.user_dir}/{chat_id}.json"
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                with open(file_path, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)

                    # messagesキーがある場合とない場合で分岐
                    messages_to_process = loaded_data.get("messages", loaded_data)
                    if not isinstance(messages_to_process, list):
                        st.error("メッセージデータが正しい形式ではありません")
                        return None

                    # メッセージを適切な形式に変換
                    formatted_messages = []
                    for msg in messages_to_process:
                        formatted_msg = {
                            'role': msg.get('role', 'unknown'),
                            'content': msg.get('content', ''),
                            'type': 'markdown' if msg.get('role') == 'assistant' else 'text',
                            'timestamp': msg.get('timestamp', '')
                        }
                        formatted_messages.append(formatted_msg)

                    return {"messages": formatted_messages}  # 辞書形式で返す
            return None
        except Exception as e:
            st.error(f"予期せぬエラー: {str(e)}")
            st.error(f"エラーの詳細: {type(e).__name__}")
            return None

    def list_chats(self) -> List[Dict]:
        """ユーザーの全チャット履歴をリスト化"""
        chats = []
        try:
            for file_name in os.listdir(self.user_dir):
                if file_name.endswith('.json'):
                    try:
                        file_path = f"{self.user_dir}/{file_name}"
                        with open(file_path, 'r', encoding='utf-8') as f:
                            chat_data = json.load(f)

                        chat_id = file_name.replace('.json', '')

                        # タイトルの整形（長すぎる場合は省略）
                        title = chat_data.get("title", "")

                        # タイムスタンプの整形
                        timestamp = chat_data.get("timestamp", "")
                        if timestamp:
                            try:
                                # タイムスタンプを日付形式に変換（必要に応じて）
                                dt = datetime.fromisoformat(timestamp)
                                formatted_time = dt.strftime("%Y-%m-%d %H:%M")
                            except:
                                formatted_time = timestamp
                        else:
                            formatted_time = "不明"

                        chats.append({
                            "id": chat_id,
                            "title": title or "無題の会話",
                            "timestamp": timestamp,  # ソート用に元のタイムスタンプを保持
                            "formatted_time": formatted_time  # 表示用
                        })
                    except Exception as e:
                        st.warning(f"ファイル {file_name} の読み込みをスキップ: {str(e)}")
                        continue

            # 新しい順にソート
            return sorted(chats, key=lambda x: x["timestamp"] or "", reverse=True)

        except Exception as e:
            st.error(f"履歴一覧の取得中にエラー: {str(e)}")
            return []

def init_chat_history():
    """チャット履歴の初期化"""
    if 'history_manager' not in st.session_state:
        username = st.session_state.get('username', 'default_user')
        # 履歴保存用ディレクトリの作成を確実に
        base_dir = "chat_histories"
        user_dir = f"{base_dir}/{username}"
        os.makedirs(user_dir, exist_ok=True)
        st.session_state.history_manager = ChatHistoryManager(username)
    if 'current_chat_id' not in st.session_state:
        st.session_state.current_chat_id = datetime.now().strftime("%Y%m%d_%H%M%S")


def add_chat_history_ui():
    """チャット履歴UIの追加"""
    with st.sidebar:
        st.divider()
        st.markdown("### 💭 会話履歴")
        # 新規チャット開始ボタン
        if st.button("✨ 新しい会話を開始"):
            st.session_state.messages = []
            st.session_state.current_chat_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.rerun()
        # 過去の会話一覧
        chats = st.session_state.history_manager.list_chats()
        for chat in chats:
            chat_title = f"{chat['title']} ({chat['timestamp'][:10]})"
            if st.button(chat_title, key=f"chat_{chat['id']}"):
                chat_data = st.session_state.history_manager.load_chat(chat['id'])
                if chat_data:
                    st.session_state.messages = chat_data["messages"]
                    st.session_state.current_chat_id = chat['id']
                    st.rerun()

def save_current_chat():
    """現在の会話を保存"""
    if hasattr(st.session_state, 'messages') and st.session_state.messages:
        try:
            # メッセージを保存可能な形式に変換
            serializable_messages = []
            for msg in st.session_state.messages:
                content = msg.get('content', '')
                # TextBlockオブジェクトの場合の処理を追加
                if hasattr(content, 'text'):  # TextBlockオブジェクトの場合
                    content = content.text
                elif isinstance(content, list) and all(hasattr(item, 'text') for item in content):
                    # TextBlockのリストの場合
                    content = ' '.join(item.text for item in content)
                elif isinstance(content, str) and "TextBlock" in content:
                    # 文字列として保存されたTextBlockの場合
                    import re
                    text_match = re.search(r"text='(.*?)'", content)
                    if text_match:
                        content = text_match.group(1)

                cleaned_msg = {
                    'role': msg.get('role'),
                    'content': str(content),  # 確実に文字列に変換
                    'timestamp': msg.get('timestamp', ''),
                }
                serializable_messages.append(cleaned_msg)

            # 保存処理
            st.session_state.history_manager.save_chat(
                st.session_state.current_chat_id,
                serializable_messages
            )
        except Exception as e:
            st.write(f"エラー発生しちゃった！😱: {str(e)}")
            import traceback
            st.write("詳細なエラー情報:")
            st.code(traceback.format_exc())

class ResponseParser:
    @staticmethod
    def parse_response(response_str: str) -> List[TextBlock]:
        # TextBlockオブジェクトのリストを抽出
        blocks = []
        # 文字列からTextBlockオブジェクトを抽出するための正規表現
        pattern = r"TextBlock\(text='(.*?)', type='(.*?)'\)"
        matches = re.finditer(pattern, response_str)
        
        for match in matches:
            text = match.group(1)
            block_type = match.group(2)
            # エスケープされた文字を適切に処理
            text = text.replace('\\n', '\n')
            blocks.append(TextBlock(text=text, type=block_type))
        
        return blocks

class MessageRenderer:
    @staticmethod
    def render_message(message: Dict[str, Union[str, List[Any]]], is_user: bool = False) -> None:
        """メッセージを適切なフォーマットで表示

        Args:
            message: 表示するメッセージの辞書
            is_user: ユーザーのメッセージかどうかのフラグ
        """
        if is_user:
            st.markdown(f"### 🦸‍♂️ ユーザー\n{message['content']}")
            return

        try:
            content = message['content']
            if isinstance(content, list):
                MessageRenderer._render_block_list(content)
            else:
                MessageRenderer._render_single_message(content)
        except Exception as e:
            st.error("メッセージの表示中にエラーが発生しました")
            if st.debug:  # デバッグモード時のみ詳細を表示
                st.exception(e)

    @staticmethod
    def _render_block_list(blocks: List[Any]) -> None:
        """ブロックリストの表示処理

        Args:
            blocks: 表示するブロックのリスト
        """
        for block in blocks:
            try:
                if hasattr(block, 'text'):
                    st.markdown(block.text)
                else:
                    st.warning("テキスト属性がありません")
            except Exception as e:
                st.error(f"ブロックの表示中にエラーが発生: {str(e)}")

    @staticmethod
    def _render_single_message(content: str) -> None:
        try:
            blocks = ResponseParser.parse_response(content)
            st.markdown(content)
        except Exception as e:
            st.error(f"メッセージのパース中にエラーが発生: {str(e)}\n{traceback.format_exc()}")

def main():
    st.set_page_config(
        page_title="Call Anthropic Api App",
        layout="wide",
        initial_sidebar_state="collapsed",
        page_icon="img/favicon_ca3.png"
    )

    # system_promptの初期化
    if 'system_prompt' not in st.session_state:
        st.session_state.system_prompt = DEFAULT_SYSTEM_PROMPT

    # 認証チェック
    if check_password():
        # 認証成功時の処理
        display_main_app()
    else:
        # 認証失敗時は何もせずに終了
        st.stop()

# メッセージ送信時の処理
def on_send_click():
    handle_message_submission()
    save_current_chat()

def handle_message_submission():
    """メッセージ送信の処理を行う関数"""
    if "user_input" not in st.session_state or not st.session_state.user_input.strip():
        return

    user_message = st.session_state.user_input.strip()

    # ユーザーメッセージを追加
    st.session_state.messages.append({
        "role": "user",
        "content": user_message,
        "timestamp": datetime.now().isoformat()
    })

    # AIレスポンスを取得
    try:
        assistant_content = get_response(user_message)
        st.session_state.messages.append({
            "role": "assistant",
            "content": assistant_content,
            "timestamp": datetime.now().isoformat()

        })
    except Exception as e:
        st.error(f"エラーが発生しました: {str(e)}")

    # 入力をクリア
    st.session_state.user_input = ""

def display_main_app():
    """メインアプリケーションの表示処理"""
    st.title("💬 Call Anthropic Api App")

    # 認証済みのユーザー名を表示
    st.sidebar.markdown(f"👤 ログインユーザー: {st.session_state.stored_username}")

    # チャット履歴の初期化
    init_chat_history()

    # セッションステート初期化
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    if len(st.session_state.messages) > MAX_HISTORY:
        st.session_state.messages = st.session_state.messages[-MAX_HISTORY:]
        save_current_chat()

    # サイドバーにコントロールを配置
    with st.sidebar:
        st.markdown("### システム設定")
        # プリセットの選択機能
        system_presets = {
            "PMに相談する": DEFAULT_SYSTEM_PROMPT,
            "ギャルに相手してもらう": GYARU_SYSTEM_PROMPT,
            "お母さんに話を聞いてもらう": MOM_SYSTEM_PROMPT,
            "使える上司とディスカッションする": BOS_SYSTEM_PROMPT
        }

        selected_preset = st.selectbox(
            "プリセット選択:",
            options=list(system_presets.keys())
        )

        if st.button("プリセットを適用"):
            st.session_state.system_prompt = system_presets[selected_preset]
            st.success(f"{selected_preset}のプリセットを適用しました")

        # システムプロンプトの編集エリア
        new_system_prompt = st.text_area(
            "システムプロンプト:",
            value=st.session_state.system_prompt,
            height=200
        )

        # システムプロンプトの更新ボタン
        if st.button("システムプロンプトを更新"):
            st.session_state.system_prompt = new_system_prompt
            st.success("システムプロンプトを更新しました")

        # チャット履歴UIを追加
        add_chat_history_ui()

    # メッセージ入力領域
    with st.container():
        st.text_area(
            "メッセージを入力してください:",
            key="user_input",
            height=100,
            placeholder="教えてほしいことをにゅうりょくしよう！！サイドバーからシステムプロンプトも修正できるぞ！プリセットを選択後、「プリセットを適用」ボタンを忘れずに押してな！！",  # プレースホルダーを追加
        )

        # 送信ボタンのレイアウト
        col1, col2 = st.columns([1, 5])
        with col1:
            st.button(
                "送信",
                use_container_width=True,
                on_click=on_send_click
            )

    # メッセージ履歴の表示
    for message in reversed(st.session_state.messages):
        with st.container():
            MessageRenderer.render_message(
                message, 
                is_user=(message["role"] == "user")
            )

if __name__ == "__main__":
    main()