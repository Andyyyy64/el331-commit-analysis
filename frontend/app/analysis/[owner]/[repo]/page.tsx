'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import Link from 'next/link'

interface CommitData {
  hash: string
  author: string
  email: string
  message: string
  date: string
}

interface KwicResult {
  context: string
  keyword: string
  left: string
  right: string
  commit_hash: string
  next_token?: string
  next_pos?: string
  sort_metric_label?: string
  sort_metric_value?: string
}

interface NgramData {
  ngram: string
  frequency: number
  rank: number
}

interface AuthorStats {
  author: string
  commit_count: number
  avg_message_length: number
  common_words: string[]
}

export default function AnalysisPage() {
  const params = useParams()
  const owner = params.owner as string
  const repo = params.repo as string
  
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [commits, setCommits] = useState<CommitData[]>([])
  const [kwicResults, setKwicResults] = useState<KwicResult[]>([])
  const [ngramData, setNgramData] = useState<NgramData[]>([])
  const [authorStats, setAuthorStats] = useState<AuthorStats[]>([])
  const [progress, setProgress] = useState(0)
  
  // KWIC検索用の状態
  const [kwicKeyword, setKwicKeyword] = useState('')
  const [kwicSearchType, setKwicSearchType] = useState('token')
  const [kwicSortType, setKwicSortType] = useState('sequential')

  // fetchAnalysisData を useCallback でメモ化
  const fetchAnalysisData = useCallback(async () => {
    setIsLoading(true)
    setError('')
    setProgress(10)

    const apiUrlBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

    try {
      setProgress(30)
      const repoResponse = await fetch(`${apiUrlBase}/analysis/repository`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          owner,
          repo
        })
      })

      if (!repoResponse.ok) {
        const errorData = await repoResponse.json().catch(() => ({ detail: 'リポジトリの取得に失敗しました' }))
        throw new Error(errorData.detail || 'リポジトリの取得に失敗しました')
      }

      const repoData = await repoResponse.json()
      setCommits(repoData.commits || [])
      setProgress(60)

      const ngramResponse = await fetch(`${apiUrlBase}/analysis/${owner}/${repo}/ngrams`)
      if (ngramResponse.ok) {
        const ngramDataResponse = await ngramResponse.json()
        setNgramData(ngramDataResponse.ngrams || [])
      }
      setProgress(80)

      const authorResponse = await fetch(`${apiUrlBase}/analysis/${owner}/${repo}/authors`)
      if (authorResponse.ok) {
        const authorDataResponse = await authorResponse.json()
        setAuthorStats(authorDataResponse.authors || [])
      }
      setProgress(100)

    } catch (err) {
      setError(err instanceof Error ? err.message : '分析データの取得中にエラーが発生しました')
    } finally {
      setIsLoading(false)
    }
  }, [owner, repo])

  useEffect(() => {
    if (owner && repo) {
      fetchAnalysisData()
    }
  }, [owner, repo, fetchAnalysisData])

  const performKwicSearch = async () => {
    if (!kwicKeyword.trim()) return

    const apiUrlBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

    try {
      const response = await fetch(`${apiUrlBase}/analysis/${owner}/${repo}/kwic?` + 
        new URLSearchParams({
          keyword: kwicKeyword,
          search_type: kwicSearchType,
          window_size: '5',
          sort_type: kwicSortType
        }))
      
      if (response.ok) {
        const data = await response.json()
        setKwicResults(data.results || [])
      }
    } catch (err) {
      console.error('KWIC検索エラー:', err)
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 py-8">
        <div className="container mx-auto px-4 max-w-6xl">
          <div className="text-center">
            <h1 className="text-3xl font-bold text-slate-900 mb-4">
              {owner}/{repo} を分析中...
            </h1>
            <Progress value={progress} className="w-full max-w-md mx-auto mb-4" />
            <p className="text-slate-600">{progress}% 完了</p>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 py-8">
        <div className="container mx-auto px-4 max-w-6xl">
          <Alert variant="destructive" className="mb-4">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
          <Link href="/">
            <Button>トップページに戻る</Button>
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 py-8">
      <div className="container mx-auto px-4 max-w-6xl">
        {/* ヘッダー */}
        <div className="mb-8">
          <div className="flex items-center gap-2 mb-4">
            <Link href="/">
              <Button variant="outline" size="sm">← 戻る</Button>
            </Link>
            <h1 className="text-3xl font-bold text-slate-900">
              {owner}/{repo} 分析結果
            </h1>
          </div>
          <div className="flex gap-2">
            <Badge variant="outline">コミット数: {commits.length}</Badge>
            <Badge variant="outline">著者数: {authorStats.length}</Badge>
          </div>
        </div>

        {/* タブ切り替えで各機能を表示 */}
        <Tabs defaultValue="kwic" className="space-y-6">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="kwic">KWIC検索</TabsTrigger>
            <TabsTrigger value="ngrams">N-gram分析</TabsTrigger>
            <TabsTrigger value="authors">著者分析</TabsTrigger>
            <TabsTrigger value="commits">コミット一覧</TabsTrigger>
          </TabsList>

          {/* KWIC検索タブ */}
          <TabsContent value="kwic" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>KWIC (Key Word in Context) 検索</CardTitle>
                <CardDescription>
                  指定したキーワードの前後の文脈を表示します
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex gap-2 mb-4">
                  <Input
                    placeholder="検索キーワードを入力"
                    value={kwicKeyword}
                    onChange={(e) => setKwicKeyword(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && performKwicSearch()}
                    className="flex-1"
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
                  </select>
                  <Button onClick={performKwicSearch}>検索</Button>
                </div>
                
                {kwicResults.length > 0 && (
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
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* N-gram分析タブ */}
          <TabsContent value="ngrams" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>N-gram分析結果</CardTitle>
                <CardDescription>
                  頻出する単語の組み合わせ
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>順位</TableHead>
                      <TableHead>N-gram</TableHead>
                      <TableHead>頻度</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {ngramData.slice(0, 20).map((item, idx) => (
                      <TableRow key={idx}>
                        <TableCell>{item.rank}</TableCell>
                        <TableCell className="font-mono">{item.ngram}</TableCell>
                        <TableCell>{item.frequency}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          {/* 著者分析タブ */}
          <TabsContent value="authors" className="space-y-4">
            <div className="grid md:grid-cols-2 gap-6">
              {authorStats.map((author, idx) => (
                <Card key={idx}>
                  <CardHeader>
                    <CardTitle className="text-lg">{author.author}</CardTitle>
                    <CardDescription>
                      コミット数: {author.commit_count} | 
                      平均文長: {author.avg_message_length.toFixed(1)}文字
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div>
                      <h4 className="font-semibold mb-2">よく使う単語:</h4>
                      <div className="flex flex-wrap gap-1">
                        {author.common_words.slice(0, 10).map((word, wordIdx) => (
                          <Badge key={wordIdx} variant="secondary" className="text-xs">
                            {word}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>

          {/* コミット一覧タブ */}
          <TabsContent value="commits" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>コミット一覧</CardTitle>
                <CardDescription>
                  取得したコミットメッセージ
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>日時</TableHead>
                      <TableHead>著者</TableHead>
                      <TableHead>メッセージ</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {commits.slice(0, 50).map((commit, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="text-sm text-slate-500">
                          {new Date(commit.date).toLocaleDateString()}
                        </TableCell>
                        <TableCell>{commit.author}</TableCell>
                        <TableCell className="max-w-md truncate">
                          {commit.message}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
} 