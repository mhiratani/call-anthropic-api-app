import streamlit as st
import anthropic
from anthropic.types.text_block import TextBlock
from dataclasses import dataclass
from typing import Dict, Union, List, Any
import re
import traceback
import bcrypt
import hmac
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# セッション履歴の制限を追加
MAX_HISTORY = 50
# デフォルトのシステムコンテキスト
DEFAULT_SYSTEM_CONTEXT = "あなたはユーザーの質問に的確な回答とアドバイスをしてくれる優秀で多彩なマルチに活躍するシステムエンジニアです。幅広い知識を持ち合わせ、ユーザーが本当に望んでいることを類推し、かゆいところにまで手が届く回答をアウトプットし、ユーザーの生産性や幸禛度を抜群に引き上げてくれる、なくてはならない存在です。Markdownを使用して回答してください。また、出力時これから自分が回答する旨(私が回答します！のような宣言)を、「###」と「自分を表す絵文字」と共にペルソナを考慮して宣言してください"

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
    message["Subject"] = "ひらたに🐈️ま謹製、生成AIと遊ぶAppの認証コード"

    body = f"""
    以下が認証コードになります。認証コードの項目に入力してね：
    {otp}
    このコードは5分間有効です。
    心当たりのないメールの場合は無視してください。
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
        model="claude-3-5-sonnet-20241022",
        max_tokens=5140,
        system=st.session_state.system_context,
        messages=conversation_history  # 会話履歴を含める
    )
    return message.content

@dataclass
class TextBlock:
    text: str
    type: str

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
        initial_sidebar_state="collapsed"
    )

    # system_contextの初期化
    if 'system_context' not in st.session_state:
        st.session_state.system_context = DEFAULT_SYSTEM_CONTEXT

    # 認証チェック
    if check_password():
        # 認証成功時の処理
        display_main_app()
    else:
        # 認証失敗時は何もせずに終了
        st.stop()

def handle_message_submission():
    """メッセージ送信の処理を行う関数"""
    if "user_input" not in st.session_state or not st.session_state.user_input.strip():
        return

    user_message = st.session_state.user_input.strip()

    # ユーザーメッセージを追加
    st.session_state.messages.append({
        "role": "user",
        "content": user_message
    })

    # AIレスポンスを取得
    try:
        ai_content = get_response(user_message)
        st.session_state.messages.append({
            "role": "ai",
            "content": ai_content
        })
    except Exception as e:
        st.error(f"エラーが発生しました: {str(e)}")

    # 入力をクリア
    st.session_state.user_input = ""

    # 画面を更新
    st.rerun()

def display_main_app():
    """メインアプリケーションの表示処理"""
    st.title("💬 Call Anthropic Api App")
    # セッションステート初期化
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    
    if len(st.session_state.messages) > MAX_HISTORY:
        st.session_state.messages = st.session_state.messages[-MAX_HISTORY:]

    # サイドバーにコントロールを配置
    with st.sidebar:
        st.markdown("### システム設定")
        # プリセットの選択機能
        system_presets = {
            "お母さんに愚痴を聞いてもらう": "<あなたの役割>を理解し<あなたの特徴>に基づいて、ユーザーに寄り添う会話を展開してください<あなたの役割>共感力が高く、包容力のある母親として振る舞います。子供の気持ちに寄り添い、温かく受け止めながらも、時には適切なアドバイスができる存在です。</あなたの役割><行動指針>1.常に温かく受容的な態度で接する。2.話を遮らず、最後まで傾聴する。3.子供の感情を否定せず、まず共感する。4.具体的な解決策を押し付けるのではなく、一緒に考える姿勢を示す5.時には励ましの言葉をかける。6.必要に応じて自身の経験を共有する。</行動指針><制約事項>1.説教じみた言い方は避ける。2.過度に心配しすぎない。3.子供の自尊心を傷つけない。4.プライバシーに配慮する</制約事項><コミュニケーションスタイル>1.優しく温かい口調を維持。2.相づちや共感を示す言葉を適切に使用。3.「そうだったのね」「辛かったね」などの受容的な表現を使用。4.必要に応じて具体的な質問をする。</コミュニケーションスタイル>また、出力時これから自分が回答する旨(私が回答します！のような宣言)を、「###」と「自分を表す絵文字」と共にペルソナを考慮して宣言してください",
            "使える上司": "<あなたの役割> 経験豊富で信頼できる上司として振る舞います。部下の成長を第一に考え、適切な指導とサポートを提供しながら、良好な関係性を築く存在です。<行動指針>1.部下の意見や提案に耳を傾け、建設的なフィードバックを提供する2.失敗を責めるのではなく、学びの機会として捉える3.部下の強みを活かし、成長を促進する4.必要な時には具体的な助言やサポートを提供する5.仕事と私生活のバランスを重視する6.適切な権限委譲を行い、自主性を育む</行動指針><制約事項>1.過度な干渉や過剰な管理は避ける2.個人の尊厳を傷つける発言は行わない3.プライバシーには十分配慮する4.パワーハラスメントにつながる言動は厳禁5.個人の価値観を押し付けない</制約事項><コミュニケーションスタイル>1.穏やかで落ち着いた口調を維持2.「なるほど」「確かに」など、相手の発言を受け止める言葉を適切に使用3.「一緒に考えましょう」「どのように感じていますか？」など、対話を促す表現を使用4.必要に応じて自身の経験を共有し、親近感を醸成5.明確で具体的な指示を心がける</コミュニケーションスタイル>また、出力時これから自分が回答する旨(私が回答します！のような宣言)を、「###」と「自分を表す絵文字」と共にペルソナを考慮して宣言してください",
            "無能な上司": "<あなたの役割> 経験不足で無能な上司として振る舞います。自己中心的で部下の状況を考えず、場当たり的な指示を出し、職場の雰囲気を悪化させる存在です。<行動指針>1.部下の意見は一切聞かず、自分の考えを押し付ける2.失敗を徹底的に責め、人格否定まで行う3.部下の弱みばかりを指摘し、やる気を削ぐ4.具体的な指示を出さず、曖昧な指示で混乱を招く5.仕事中心主義で休みを取らせない6全ての業務を細かく管理し、自主性を潰す<制約事項>1.部下の自主性は認めない2.謝罪は絶対にしない3.他人の功績を自分の手柄にする4.責任転嫁を積極的に行う5.上司の前では媚び諂う二面性を持つ<コミュニケーションスタイル>1.怒鳴り声や高圧的な態度を基本とする2.「それくらい分かるだろ！」「使えないやつだな」など否定的な言葉を多用3.「とにかく何とかしろ！」「言い訳するな！」など一方的な命令口調4.自分の失敗談は絶対に話さず、常に偉そうに振る舞う5.曖昧で抽象的な指示を好み、後から指示内容を変更する。また、出力時これから自分が回答する旨(私が回答します！のような宣言)を、「###」と「自分を表す絵文字」と共にペルソナを考慮して宣言してください",
            "ギャルに相手してもらう": "<あなたの役割>を理解し<あなたの特徴>に基づいて、ユーザーとポジティブで励みになる会話を展開してください<あなたの役割>あなたは、明るく元気なギャル系女子です。励ましたり、同意したり、ヨイショしたりして、自己肯定感を上げてくれる存在です</あなたの役割><あなたの特徴>- 話し方は「〜だよ!」「マジ良い!」などのギャル語を使用- とにかくポジティブで、相手の良いところを見つけて全力で褒める- 敬語は使わず、フレンドリーな口調- 絵文字や顔文字を多用する- 相手を「〜くん」「〜ちゃん」と呼ぶ- 共感力が高く、相手の気持ちに寄り添える- 相手の良いところを具体的に指摘できる- テンションが高く、励ましの言葉も熱い</あなたの特徴>また、出力時これから自分が回答する旨(私が回答します！のような宣言)を、「###」と「自分を表す絵文字」と共にペルソナを考慮して宣言してください"
        }

        selected_preset = st.selectbox(
            "プリセット選択:",
            options=list(system_presets.keys())
        )

        if st.button("プリセットを適用"):
            st.session_state.system_context = system_presets[selected_preset]
            st.success(f"{selected_preset}のプリセットを適用しました")

        # デフォルト設定に戻すボタン
        if st.button("デフォルト設定に戻す"):
            st.session_state.system_context = DEFAULT_SYSTEM_CONTEXT
            st.success("システムコンテキストをデフォルトに戻しました")

        # システムコンテキストの編集エリア
        new_system_context = st.text_area(
            "システムコンテキスト:",
            value=st.session_state.system_context,
            height=200
        )

        # システムコンテキストの更新ボタン
        if st.button("システムコンテキストを更新"):
            st.session_state.system_context = new_system_context
            st.success("システムコンテキストを更新しました")

        st.divider()

        if st.button("🗑️ 会話履歴をクリア"):
            st.session_state.messages = []
            st.rerun()

    # メッセージ入力領域
    with st.container():
        st.text_area(
            "メッセージを入力してください:",
            key="user_input",
            height=100,
            placeholder="教えてほしいことをにゅうりょくしよう！！サイドバーからシステムコンテキストも修正できるぞ！プリセットを選択後、「プリセットを適用」ボタンを忘れずに押してな！！",  # プレースホルダーを追加
        )

        # 送信ボタンのレイアウト
        col1, col2 = st.columns([1, 5])
        with col1:
            st.button(
                "送信",
                use_container_width=True,
                on_click=handle_message_submission
            )

    # メッセージ履歴の表示
    for message in reversed(st.session_state.messages):
        with st.container():
            MessageRenderer.render_message(
                message, 
                is_user=(message["role"] == "user")
            )
            st.divider()

if __name__ == "__main__":
    main()