# Pythonの公式イメージをベースとして使用
FROM python:3.9-slim

# 作業ディレクトリを設定
WORKDIR /app

# 依存関係ファイルをコピー
COPY requirements.txt requirements.txt

# 依存関係をインストール
# --no-cache-dir: キャッシュを無効化してイメージサイズを削減
# --compile: pycファイルを事前にコンパイル (オプション)
RUN pip install --no-cache-dir -r requirements.txt

# spaCyの言語モデルをダウンロード (Dockerfile内で実行)
RUN python -m spacy download en_core_web_sm

# アプリケーションコードをコピー
COPY ./app /app/app

# 環境変数 (例: PORT)
ENV PORT 8000

# ポートを開放
EXPOSE 8000

# アプリケーションの起動コマンド
# app.main:app の app は FastAPIインスタンスを指す
CMD ["python", "app/main.py"] 