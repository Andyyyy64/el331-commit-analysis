# Git Commit Fingerprint Analyzer - Backend

このディレクトリには、Python FastAPIを使用したバックエンドアプリケーションのコードが含まれています。

## セットアップ (ローカル環境)

1.  Python 3.9+ がインストールされていることを確認してください。
2.  この `backend` ディレクトリで仮想環境を作成し、アクティベートします:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # macOS/Linux の場合
    # venv\Scripts\activate    # Windows の場合
    ```
3.  依存関係をインストールします:
    ```bash
    pip install -r requirements.txt
    ```
4.  (初回のみ) spaCyの英語言語モデルをダウンロードします:
    ```bash
    python -m spacy download en_core_web_sm
    # 日本語のコミットメッセージも分析対象とする場合は、日本語モデルもダウンロードします。
    # python -m spacy download ja_core_news_sm
    ```
5.  (重要) GitHub Personal Access Token (PAT) を設定します。
    プロジェクトルートの `README.md` の「GitHub Personal Access Token (PAT) の設定 (重要)」セクションを参照し、
    この `backend` ディレクトリ直下に `.env` ファイルを作成して `GITHUB_PAT` を設定してください。

    **注記:** 以前Poetryを使用していた場合、このディレクトリ内の `pyproject.toml` と `poetry.lock` は不要になりました。必要に応じて手動で削除してください。

## 開発サーバーの起動 (ローカル環境)

```bash
python -m app.main
```

APIのドキュメントは `http://localhost:8000/docs` および `http://localhost:8000/redoc` で自動的に生成されます。

## Docker を使用した実行

Docker を使用してバックエンドを実行する方法については、プロジェクトルートの `README.md` を参照してください。

## 主な技術スタック

*   FastAPI: 高パフォーマンスなAPI開発フレームワーク
*   spaCy: 自然言語処理ライブラリ (トークン化、品詞タギング、固有表現認識など)
*   scikit-learn: 機械学習ライブラリ (著者識別など)
*   requests: HTTPリクエスト用ライブラリ (GitHub API連携)
*   python-dotenv: 環境変数管理

## ディレクトリ構成

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py             # FastAPI アプリケーションインスタンス
│   ├── routers/            # APIエンドポイントの定義
│   │   ├── __init__.py
│   │   └── analysis.py     # 分析関連エンドポイント
│   ├── services/           # ビジネスロジック
│   │   ├── __init__.py
│   │   ├── git_service.py  # GitHub API データ取得処理
│   │   └── nlp_service.py  # NLP処理 (KWIC, N-gram, 著者分析)
│   ├── models/             # Pydanticモデル (リクエスト/レスポンス)
│   │   ├── __init__.py
│   │   └── analysis_models.py
│   └── core/               # 設定ファイル、共通ロジック
│       ├── __init__.py
│       └── config.py       # 環境変数読み込みなど
├── Dockerfile              # Dockerイメージビルド用
├── requirements.txt        # Python依存関係リスト
├── .env.example            # 環境変数ファイルテンプレート (オプション)
└── README.md               # このファイル
``` 