# Git Commit Fingerprint Analyzer - Frontend

このディレクトリには、Next.js (App Router, TypeScript, Tailwind CSS) を使用したフロントエンドアプリケーションのコードが含まれています。

## セットアップ (ローカル環境)

1.  Node.js 18+ と npm がインストールされていることを確認してください。
2.  (まだの場合) この `frontend` ディレクトリで、以下のコマンドを実行して依存関係をインストールします:
    ```bash
    npm install
    ```

## 開発サーバーの起動 (ローカル環境)

```bash
npm run dev
```

アプリケーションはデフォルトで `http://localhost:3000` でアクセスできます。

## Docker を使用した実行

Docker を使用してフロントエンドを実行する方法については、プロジェクトルートの `README.md` を参照してください。

## 主な技術スタック

*   **Next.js 13+ (App Router)**: Reactベースのフレームワーク。最新のApp Routerを採用しています。
*   **TypeScript**: 静的型付けを提供し、開発効率とコードの堅牢性を向上させます。
*   **Tailwind CSS**: ユーティリティファーストのCSSフレームワークで、効率的なスタイリングを可能にします。
*   **ESLint**: コードの静的解析ツールで、品質を保ちます。
*   **shadcn/ui**: 再利用可能なUIコンポーネント群。

## ディレクトリ構成 (App Router)

```
frontend/
├── app/
│   ├── (components)/       # UIコンポーネント (shadcn/uiにより自動生成されるものも含む)
│   ├── analysis/
│   │   └── [owner]/
│   │       └── [repo]/
│   │           └── page.tsx      # 分析結果表示ページ
│   ├── lib/
│   │   └── utils.ts        # shadcn/uiユーティリティ
│   ├── globals.css
│   ├── layout.tsx
│   └── page.tsx            # トップページ
├── components/
│   └── ui/                 # shadcn/uiコンポーネント
├── public/
├── .eslintrc.json
├── .gitignore
├── Dockerfile              # Dockerイメージビルド用
├── next.config.ts
├── package.json
├── README.md               # このファイル
├── tsconfig.json
└── package-lock.json
```

## バックエンドAPIについて

このフロントエンドアプリケーションは、バックエンドAPIと連携します。
ローカル開発環境では、バックエンドAPIが `http://localhost:8000` で実行されていることを想定しています。
Docker Composeで実行する場合、APIのURLは環境変数 `NEXT_PUBLIC_API_URL` (例: `http://backend:8000/api`) を通じて自動的に設定されます。

## 今後の開発予定

*   リポジトリ入力フォームの実装
*   バックエンドAPIとの連携 (コミットデータ取得、KWIC分析、N-gram分析など)
*   分析結果の表示用UIコンポーネントの開発
*   コミュニケーションスタイルプロファイルの可視化 