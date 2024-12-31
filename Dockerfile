FROM python:3.9-slim

WORKDIR /app

# システムの依存関係をインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# 必要なPythonパッケージをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのソースコードをコピー
COPY . .

# 環境変数を設定
ENV PORT=8510

# ポートを公開
EXPOSE 8510

# アプリケーションを実行
ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8510", "--server.address=0.0.0.0"]