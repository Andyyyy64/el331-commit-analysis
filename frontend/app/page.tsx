'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { useRouter } from 'next/navigation'

export default function Home() {
  const [repoUrl, setRepoUrl] = useState('')
  const [username, setUsername] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [isUserAnalyzing, setIsUserAnalyzing] = useState(false)
  const [error, setError] = useState('')
  const [userError, setUserError] = useState('')
  const router = useRouter()

  const parseGitHubUrl = (url: string) => {
    const patterns = [
      /github\.com\/([^\/]+)\/([^\/]+)/,
      /^([^\/]+)\/([^\/]+)$/
    ]
    
    for (const pattern of patterns) {
      const match = url.match(pattern)
      if (match) {
        return {
          owner: match[1],
          repo: match[2].replace(/\.git$/, '')
        }
      }
    }
    return null
  }

  const parseGitHubUsername = (input: string) => {
    const patterns = [
      /github\.com\/([^\/]+)$/,
      /^([^\/]+)$/
    ]
    
    for (const pattern of patterns) {
      const match = input.match(pattern)
      if (match) {
        return match[1]
      }
    }
    return null
  }

  const handleAnalyze = async () => {
    if (!repoUrl.trim()) {
      setError('リポジトリURLまたはオーナー/リポジトリ名を入力してください')
      return
    }

    const parsed = parseGitHubUrl(repoUrl.trim())
    if (!parsed) {
      setError('有効なGitHubリポジトリURLまたは "owner/repo" 形式で入力してください')
      return
    }

    setError('')
    setIsAnalyzing(true)

    try {
      router.push(`/analysis/${parsed.owner}/${parsed.repo}`)
    } catch (err) {
      console.error('Navigation error:', err)
      setError('分析ページの表示に失敗しました')
      setIsAnalyzing(false)
    }
  }

  const handleUserAnalyze = async () => {
    if (!username.trim()) {
      setUserError('GitHubユーザー名またはプロフィールURLを入力してください')
      return
    }

    const parsed = parseGitHubUsername(username.trim())
    if (!parsed) {
      setUserError('有効なGitHubユーザー名またはプロフィールURLを入力してください')
      return
    }

    setUserError('')
    setIsUserAnalyzing(true)

    try {
      // APIエンドポイントを環境変数から取得、なければデフォルト値
      const apiUrlBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
      const response = await fetch(`${apiUrlBase}/analysis/user`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username: parsed }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'ユーザー分析の準備に失敗しました。' }));
        throw new Error(errorData.detail || `ユーザー分析の準備に失敗しました: ${response.status}`);
      }
      
      // 成功したらページ遷移
      router.push(`/analysis/user/${parsed}`)
    } catch (err) {
      console.error('User analysis initiation error:', err)
      setUserError(err instanceof Error ? err.message : 'ユーザー分析の開始に失敗しました。')
    } finally {
      setIsUserAnalyzing(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 py-8">
      <div className="container mx-auto px-4 max-w-4xl">
        {/* ヘッダー */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-slate-900 mb-4">
            Git Commit Fingerprint Analyzer
          </h1>
          <p className="text-xl text-slate-600 mb-2">
            GitHubリポジトリのコミットメッセージを分析し、開発者のコミュニケーションスタイルを可視化
          </p>
          <div className="flex justify-center gap-2 mt-4">
            <Badge variant="secondary">KWIC分析</Badge>
            <Badge variant="secondary">N-gram分析</Badge>
            <Badge variant="secondary">著者識別</Badge>
            <Badge variant="secondary">スタイル分析</Badge>
          </div>
        </div>

        {/* 分析オプション */}
        <div className="grid md:grid-cols-1 gap-6 mb-8">
          {/* リポジトリ分析 */}
          <Card>
            <CardHeader>
              <CardTitle>リポジトリ分析</CardTitle>
              <CardDescription>
                特定のGitHubリポジトリのコミットメッセージを分析します
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Input
                  placeholder="例: microsoft/vscode または https://github.com/microsoft/vscode"
                  value={repoUrl}
                  onChange={(e) => setRepoUrl(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleAnalyze()}
                  className="flex-1"
                />
                <Button 
                  onClick={handleAnalyze} 
                  disabled={isAnalyzing}
                  className="min-w-[120px]"
                >
                  {isAnalyzing ? '分析中...' : '分析開始'}
                </Button>
              </div>
              
              {error && (
                <Alert variant="destructive">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>

          {/* ユーザー分析 */}
          <Card>
            <CardHeader>
              <CardTitle>ユーザー分析</CardTitle>
              <CardDescription>
                GitHubユーザーのすべての公開リポジトリからコミットメッセージを収集して分析します
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex gap-2">
                <Input
                  placeholder="例: torvalds または https://github.com/torvalds"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleUserAnalyze()}
                  className="flex-1"
                />
                <Button 
                  onClick={handleUserAnalyze} 
                  disabled={isUserAnalyzing}
                  className="min-w-[120px]"
                >
                  {isUserAnalyzing ? '分析中...' : '分析開始'}
                </Button>
              </div>
              
              {userError && (
                <Alert variant="destructive">
                  <AlertDescription>{userError}</AlertDescription>
                </Alert>
              )}
              
              <Alert>
                <AlertDescription>
                  <strong>注意:</strong> ユーザー分析は多くのリポジトリとコミットを処理するため、
                  完了まで時間がかかる場合があります。
                </AlertDescription>
              </Alert>
            </CardContent>
          </Card>

          {/* N-gram比較分析への導線カードを追加 */}
          <Card>
            <CardHeader>
              <CardTitle>N-gram 比較分析</CardTitle>
              <CardDescription>
                2つのリポジトリまたはユーザー間で、N-gram (単語の組み合わせ) の出現パターンを比較します。
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button onClick={() => router.push('/compare/ngrams')} className="w-full">
                N-gram比較ページへ
              </Button>
            </CardContent>
          </Card>
        </div>

        {/* 機能説明 */}
        <div className="grid md:grid-cols-2 gap-6 mb-8">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">KWIC (Key Word in Context)</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-slate-600">
                指定したキーワード（単語、品詞、固有表現）の前後5語を表示し、
                コミットメッセージ内での使用文脈を可視化します。
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">N-gram分析</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-slate-600">
                頻繁に使用される単語の組み合わせ（N-gram）を特定し、
                開発者の表現パターンを分析します。
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">著者識別</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-slate-600">
                コミットメッセージの文体的特徴から著者を推定する
                機械学習モデルを試作します。
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">スタイル分析</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-slate-600">
                言語的特徴に基づく開発者のコミュニケーション傾向を
                可視化します（科学的診断ではありません）。
              </p>
            </CardContent>
          </Card>
        </div>

        {/* 注意事項 */}
        <Alert>
          <AlertDescription>
            <strong>注意:</strong> このツールは公開リポジトリのみを対象とし、
            コミットメッセージの言語的特徴に基づく傾向分析を行います。
            結果は参考程度にご利用ください。
          </AlertDescription>
        </Alert>
      </div>
    </div>
  )
}
