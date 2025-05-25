# Node.jsの公式イメージをベースとして使用 (バージョンはプロジェクトに合わせて調整)
FROM node:18-alpine

# 作業ディレクトリを設定
WORKDIR /app

# package.json と package-lock.json (または yarn.lock) をコピー
COPY package.json package-lock.json* ./
# COPY yarn.lock ./

# 依存関係をインストール (npm を使用)
RUN npm install

# アプリケーションコードをコピー
COPY . .

# Next.jsアプリケーションをビルド
RUN npm run build

# 環境変数 (例: PORT)
ENV PORT 3000
# Next.jsが使用するポート (デフォルトは3000だが、明示的に設定する)
ENV NEXT_PUBLIC_PORT 3000

# ポートを開放
EXPOSE 3000

# アプリケーションの起動コマンド
CMD ["npm", "start"] 