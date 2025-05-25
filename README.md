## 概要

このプロジェクトは、指定された公開GitHubリポジトリのコミットメッセージを分析し、以下の機能を提供することを目的としています。

*   **KWIC (Key Word in Context) 表示**: コミットメッセージ中の特定のキーワード（単語、品詞、固有表現など）を、その文脈と共に表示します。
*   **N-gram分析**: コミットメッセージ内で頻繁に使用される単語の組み合わせ（N-gram）を特定し、表示します。
*   **著者識別 (試作)**: コミットメッセージの文体的な特徴から、メッセージの著者を推定する機能を試作します。
*   **コミュニケーションスタイル分析 (試作)**: コミットメッセージの言語的な特徴に基づき、開発者のコミュニケーション上の傾向やスタイルを推定し、可視化することを試みます。（**注:** これはあくまで言語的特徴に基づく傾向分析であり、科学的に確立された性格診断ではありません。）

このアプリケーションは、バックエンドにPython (FastAPI)、フロントエンドにNext.js (TypeScript) を使用しています。

## 技術スタック

*   **バックエンド**: Python 3.9+, FastAPI, spaCy, scikit-learn, requests, python-dotenv
*   **フロントエンド**: Node.js 18+, Next.js 13+ (App Router), TypeScript, Tailwind CSS
*   **開発ツール**: Docker, Docker Compose

## ディレクトリ構成

```
/
├── backend/      # Python/FastAPI バックエンドコード
│   ├── app/      # FastAPIアプリケーションモジュール
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/     # Next.js/TypeScript フロントエンドコード
│   ├── Dockerfile
│   └── package.json
├── docs/
│   └── server-api.md # APIドキュメント
├── .gitignore
├── docker-compose.yaml
└── README.md     # このファイル
```

## 環境構築と実行方法

### 前提条件

*   Docker Desktop (またはDocker EngineとDocker Compose)
*   Git

### GitHub Personal Access Token (PAT) の設定 (重要)

本アプリケーションはGitHub APIを利用してコミットデータを取得します。
APIのレートリミットを緩和するために、GitHub Personal Access Token (PAT) の設定が**強く推奨**されます。

1.  GitHubでPATを発行します。スコープはデフォルトで
2.  プロジェクトの `backend` ディレクトリ直下に `.env` という名前のファイルを作成します。
3.  `.env` ファイルに以下のようにPATを記述します:
    ```env
    GITHUB_PAT=あなたのGitHubPAT
    ```
    例: `GITHUB_PAT=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

    **注意:** `.env` ファイルは `.gitignore` によりGitの追跡対象外となっていますので、PATがリポジトリにコミットされることはありません。

### Docker Compose を使用した実行 (推奨)

1.  **(初回のみ)** Dockerイメージをビルドします:
    ```bash
    docker compose build
    ```
2.  アプリケーションを起動します:
    ```bash
    docker compose up
    ```
    (バックグラウンドで起動する場合は `docker compose up -d`)

    *   フロントエンドは `http://localhost:3000` でアクセスできます。
    *   バックエンドAPIは `http://localhost:8000` でアクセスできます。(FastAPIドキュメント: `http://localhost:8000/docs`)

3.  アプリケーションを停止するには:
    ```bash
    docker compose down
    ```

### ローカルでの個別実行 (非推奨・デバッグ用)

#### バックエンド (Python / FastAPI)

1.  `backend` ディレクトリに移動します:
    ```bash
    cd backend
    ```
2.  仮想環境を作成し、アクティベートします (例: venv):
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # macOS/Linux
    # venv\Scripts\activate    # Windows
    ```
3.  依存関係をインストールします:
    ```bash
    pip install -r requirements.txt
    ```
4.  (初回のみ) spaCyの英語言語モデルをダウンロードします:
    ```bash
    python -m spacy download en_core_web_sm
    ```
5.  開発サーバーを起動します:
    ```bash
    python app/main.py
    ```

#### フロントエンド (Next.js)

1.  `frontend` ディレクトリに移動します:
    ```bash
    cd frontend
    ```
2.  依存関係をインストールします:
    ```bash
    npm install
    ```
3.  開発サーバーを起動します:
    ```bash
    npm run dev
    ```

## APIドキュメント

バックエンドAPIの仕様については、`docs/server-api.md` を参照してください。
