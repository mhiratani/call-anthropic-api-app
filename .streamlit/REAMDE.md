## 🌟 特徴

- 2段階認証によるセキュアなログイン機能
  - ユーザー名/パスワード認証
  - メールによるOTP認証
- 複数のプリセットペルソナ
  - お母さん
  - できる上司
  - できない上司
  - ギャル
- カスタマイズ可能なシステムコンテキスト
- Markdown対応の会話表示
- 会話履歴の保持（最大50メッセージ）

## 🔧 必要な環境

- Python 3.7以上
- Streamlit
- Anthropic API key
- SMTPサーバーアクセス（メール認証用）

## 📦 必要なパッケージ

```bash
pip install streamlit
pip install anthropic
pip install bcrypt
```

## 🔑 環境設定
- 以下の情報を.streamlit/secrets.tomlに設定する必要があります：

```toml
[api_key]
anthropic = "your-anthropic-api-key"

[email]
smtp_server = "smtp.example.com"
smtp_port = 587
sender_email = "your-email@example.com"
sender_password = "your-email-password"

[credentials.user1]
username = "username1"
password = "password1"
email = "user1@example.com"
```