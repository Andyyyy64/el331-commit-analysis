'use client'

import { useParams } from 'next/navigation'
import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ArrowLeft, User, GitBranch, MessageCircle, Clock } from 'lucide-react'
import Link from 'next/link'

interface Commit {
  hash: string
  author: string
  email: string
  message: string
  date: string
  repository: string
}

interface UserAnalysisResponse {
  username: string
  repositories: string[]
  commits: Commit[]
  total_commits: number
  total_repositories: number
}

interface KwicResult {
  context: string
  keyword: string
  left: string
  right: string
  commit_hash: string
  sort_metric_label?: string
  sort_metric_value?: string
}

interface NgramResult {
  ngram: string
  frequency: number
  rank: number
}

interface AuthorStat {
  author: string
  email: string
  commit_count: number
  avg_message_length: number
  common_words: string[]
  total_chars: number
}

export default function UserAnalysisPage() {
  const params = useParams()
  const username = params?.username as string

  const [analysisData, setAnalysisData] = useState<UserAnalysisResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  // KWIC検索
  const [kwicKeyword, setKwicKeyword] = useState('')
  const [kwicResults, setKwicResults] = useState<KwicResult[]>([])
  const [isKwicLoading, setIsKwicLoading] = useState(false)
  const [kwicSearchType, setKwicSearchType] = useState('token')
  const [kwicSortType, setKwicSortType] = useState('sequential')

  // N-gram分析
  const [ngramResults, setNgramResults] = useState<NgramResult[]>([])
  const [isNgramLoading, setIsNgramLoading] = useState(false)

  // 著者分析
  const [authorResults, setAuthorResults] = useState<AuthorStat[]>([])
  const [isAuthorLoading, setIsAuthorLoading] = useState(false)

  useEffect(() => {
    if (username) {
      analyzeUser()
    }
  }, [username])

  const analyzeUser = async () => {
    setIsLoading(true)
    setError('')
    
    try {
      const response = await fetch(`http://localhost:8000/api/analysis/user`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username }),
      })

      if (!response.ok) {
        throw new Error(`分析に失敗しました: ${response.status}`)
      }

      const data = await response.json()
      setAnalysisData(data)
    } catch (err) {
      console.error('Analysis error:', err)
      setError(err instanceof Error ? err.message : '分析中にエラーが発生しました')
    } finally {
      setIsLoading(false)
    }
  }

  const performKwicSearch = async () => {
    if (!kwicKeyword.trim()) return
    
    setIsKwicLoading(true)
    try {
      const apiUrlBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
      const response = await fetch(
        `${apiUrlBase}/analysis/user/${username}/kwic?` + 
        new URLSearchParams({
          keyword: kwicKeyword,
          search_type: kwicSearchType, 
          window_size: '5',
          sort_type: kwicSortType
        })
      )
      
      if (!response.ok) {
        throw new Error('KWIC検索に失敗しました')
      }
      
      const data = await response.json()
      setKwicResults(data.results || [])
    } catch (err) {
      console.error('KWIC search error:', err)
    } finally {
      setIsKwicLoading(false)
    }
  }

  const performNgramAnalysis = async () => {
    setIsNgramLoading(true)
    try {
      const response = await fetch(
        `http://localhost:8000/api/analysis/user/${username}/ngrams?n=2&min_frequency=3`
      )
      
      if (!response.ok) {
        throw new Error('N-gram分析に失敗しました')
      }
      
      const data = await response.json()
      setNgramResults(data.ngrams || [])
    } catch (err) {
      console.error('N-gram analysis error:', err)
    } finally {
      setIsNgramLoading(false)
    }
  }

  const performAuthorAnalysis = async () => {
    setIsAuthorLoading(true)
    try {
      const response = await fetch(
        `http://localhost:8000/api/analysis/user/${username}/authors`
      )
      
      if (!response.ok) {
        throw new Error('著者分析に失敗しました')
      }
      
      const data = await response.json()
      setAuthorResults(data.authors || [])
    } catch (err) {
      console.error('Author analysis error:', err)
    } finally {
      setIsAuthorLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 flex items-center justify-center">
        <Card className="w-96">
          <CardContent className="pt-6">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <h2 className="text-lg font-semibold mb-2">ユーザーを分析中...</h2>
              <p className="text-slate-600">
                {username} のすべての公開リポジトリからコミットを収集しています
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 py-8">
        <div className="container mx-auto px-4 max-w-4xl">
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
          <Link href="/">
            <Button variant="outline">
              <ArrowLeft className="mr-2 h-4 w-4" />
              ホームに戻る
            </Button>
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 py-8">
      <div className="container mx-auto px-4 max-w-6xl">
        {/* ヘッダー */}
        <div className="mb-6">
          <Link href="/">
            <Button variant="outline" className="mb-4">
              <ArrowLeft className="mr-2 h-4 w-4" />
              ホームに戻る
            </Button>
          </Link>
          
          <div className="flex items-center gap-3 mb-4">
            <User className="h-8 w-8" />
            <div>
              <h1 className="text-3xl font-bold text-slate-900">
                {username} のコミット分析
              </h1>
              <p className="text-slate-600">
                すべての公開リポジトリからのコミットメッセージ分析結果
              </p>
            </div>
          </div>
        </div>

        {/* 統計情報 */}
        {analysisData && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center">
                  <GitBranch className="h-4 w-4 text-blue-600" />
                  <div className="ml-2">
                    <p className="text-2xl font-bold">{analysisData.total_repositories}</p>
                    <p className="text-xs text-slate-600">リポジトリ</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center">
                  <MessageCircle className="h-4 w-4 text-green-600" />
                  <div className="ml-2">
                    <p className="text-2xl font-bold">{analysisData.total_commits}</p>
                    <p className="text-xs text-slate-600">コミット</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center">
                  <Clock className="h-4 w-4 text-purple-600" />
                  <div className="ml-2">
                    <p className="text-2xl font-bold">
                      {analysisData.total_commits > 0 ? Math.round(analysisData.total_commits / analysisData.total_repositories) : 0}
                    </p>
                    <p className="text-xs text-slate-600">平均コミット/リポジトリ</p>
                  </div>
                </div>
              </CardContent>
            </Card>
            
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center">
                  <User className="h-4 w-4 text-orange-600" />
                  <div className="ml-2">
                    <p className="text-2xl font-bold">{analysisData.repositories.length}</p>
                    <p className="text-xs text-slate-600">分析済みリポジトリ</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* タブメニュー */}
        <Tabs defaultValue="overview" className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="overview">概要</TabsTrigger>
            <TabsTrigger value="kwic">KWIC検索</TabsTrigger>
            <TabsTrigger value="ngrams">N-gram分析</TabsTrigger>
            <TabsTrigger value="authors">著者分析</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>リポジトリ一覧</CardTitle>
                <CardDescription>分析対象となった公開リポジトリ</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                  {analysisData?.repositories.map((repo, index) => (
                    <Badge key={index} variant="secondary" className="text-sm">
                      {repo}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>最近のコミット</CardTitle>
                <CardDescription>最新の10件のコミットメッセージ</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {analysisData?.commits.slice(0, 10).map((commit, index) => (
                    <div key={index} className="border-l-4 border-blue-200 pl-4 py-2">
                      <div className="flex items-center gap-2 mb-1">
                        <code className="text-xs bg-slate-100 px-2 py-1 rounded">
                          {commit.hash.substring(0, 8)}
                        </code>
                        <Badge variant="outline" className="text-xs">
                          {commit.repository}
                        </Badge>
                        <span className="text-xs text-slate-500">
                          {new Date(commit.date).toLocaleDateString('ja-JP')}
                        </span>
                      </div>
                      <p className="text-sm text-slate-700">{commit.message}</p>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="kwic" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>KWIC検索</CardTitle>
                <CardDescription>キーワードの使用文脈を確認</CardDescription>
                <p className="text-sm text-slate-500">
                  「品詞 (POS)」で検索すると、名詞 (NOUN)、動詞 (VERB) など、単語の種類を指定して検索できます。
                </p>
                <ul className="text-sm text-slate-500 list-disc pl-5 mt-1">
                  <li><strong>単語:</strong> 入力した通りの単語・フレーズを検索します。</li>
                  <li><strong>品詞 (POS):</strong> NOUN (名詞), VERB (動詞) など、品詞タグで検索します。</li>
                  <li><strong>固有表現:</strong> PERSON (人名), ORG (組織名) など、固有表現タイプで検索します。</li>
                </ul>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2">
                  <Input
                    placeholder="検索キーワードを入力"
                    value={kwicKeyword}
                    onChange={(e) => setKwicKeyword(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && performKwicSearch()}
                  />
                  <select 
                    value={kwicSearchType} 
                    onChange={(e) => setKwicSearchType(e.target.value)}
                    className="px-3 py-2 border rounded-md"
                  >
                    <option value="token">単語</option>
                    <option value="pos">品詞</option>
                    <option value="entity">固有表現</option>
                  </select>
                  <select 
                    value={kwicSortType} 
                    onChange={(e) => setKwicSortType(e.target.value)}
                    className="px-3 py-2 border rounded-md"
                  >
                    <option value="sequential">出現順</option>
                    <option value="next_token_frequency">後続単語頻度順</option>
                    <option value="next_pos_frequency">後続品詞頻度順</option>
                    <option value="next_token_pos_combination_frequency">後続トークン・品詞頻度順</option>
                  </select>
                  <Button onClick={performKwicSearch} disabled={isKwicLoading}>
                    {isKwicLoading ? '検索中...' : '検索'}
                  </Button>
                </div>
                
                <div className="space-y-2">
                  {kwicResults.map((result, idx) => (
                    <div key={idx} className="p-3 bg-slate-50 rounded-lg border">
                      <div className="font-mono text-sm mb-1">
                        <span className="text-slate-600">{result.left}</span>
                        <span className="bg-yellow-200 px-1 font-bold">{result.keyword}</span>
                        <span className="text-slate-600">{result.right}</span>
                      </div>
                      <div className="text-xs text-slate-500 flex justify-between items-center">
                        <span>Commit: {result.commit_hash}</span>
                        {result.sort_metric_label && result.sort_metric_value && (
                          <span className="bg-slate-200 text-slate-700 px-2 py-0.5 rounded-full text-xs">
                            {result.sort_metric_label}: {result.sort_metric_value}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="ngrams" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>N-gram分析</CardTitle>
                <CardDescription>頻出する単語の組み合わせ</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Button onClick={performNgramAnalysis} disabled={isNgramLoading}>
                  {isNgramLoading ? '分析中...' : 'N-gram分析を実行'}
                </Button>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {ngramResults.slice(0, 20).map((ngram, index) => (
                    <div key={index} className="flex justify-between items-center p-3 bg-slate-50 rounded">
                      <span className="font-medium">{ngram.ngram}</span>
                      <Badge variant="secondary">{ngram.frequency}回</Badge>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="authors" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>著者分析</CardTitle>
                <CardDescription>コミット著者の統計情報</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Button onClick={performAuthorAnalysis} disabled={isAuthorLoading}>
                  {isAuthorLoading ? '分析中...' : '著者分析を実行'}
                </Button>
                
                <div className="space-y-4">
                  {authorResults.map((author, index) => (
                    <Card key={index}>
                      <CardContent className="pt-4">
                        <div className="flex justify-between items-start mb-2">
                          <div>
                            <h3 className="font-semibold">{author.author}</h3>
                            <p className="text-sm text-slate-600">{author.email}</p>
                          </div>
                          <Badge variant="outline">
                            {author.commit_count} コミット
                          </Badge>
                        </div>
                        <p className="text-sm text-slate-600 mb-2">
                          平均メッセージ長: {Math.round(author.avg_message_length)} 文字
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {author.common_words.slice(0, 10).map((word, idx) => (
                            <Badge key={idx} variant="secondary" className="text-xs">
                              {word}
                            </Badge>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
} 