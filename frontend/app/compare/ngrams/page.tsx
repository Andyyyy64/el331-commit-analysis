'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import Link from 'next/link'
import { ArrowLeft, BarChartHorizontalBig, Repeat } from 'lucide-react'

// Types from backend (simplified for frontend)
interface NgramComparisonRequestData {
  source_type: string; // "repository" or "user"
  identifier: string;  // e.g., "owner/repo" or "username"
}

interface NgramComparisonRequest {
  source_q: NgramComparisonRequestData;
  source_k: NgramComparisonRequestData;
  ngram_n_values: number[];
  step_size: number;
  max_rank: number;
  min_frequency_q: number;
  min_frequency_k: number;
}

interface NgramComparisonStepResult {
  ngram_n: number;
  rank_start: number;
  rank_end: number;
  common_ngrams: string[];
  common_ngrams_count: number;
  source_q_ngrams_in_step: string[];
  source_k_ngrams_in_step: string[];
}

interface NgramComparisonResponse {
  request_params: NgramComparisonRequest;
  results_by_n: Record<number, NgramComparisonStepResult[]>; // Dict[int, List[...]]
  error_message?: string;
}


export default function NgramComparePage() {
  const [sourceQType, setSourceQType] = useState('repository');
  const [sourceQIdentifier, setSourceQIdentifier] = useState('');
  const [sourceKType, setSourceKType] = useState('repository');
  const [sourceKIdentifier, setSourceKIdentifier] = useState('');
  
  const [ngramNValues, setNgramNValues] = useState<number[]>([2]); // Default to bigram
  const [stepSize, setStepSize] = useState(20);
  const [maxRank, setMaxRank] = useState(200);
  const [minFrequencyQ, setMinFrequencyQ] = useState(2);
  const [minFrequencyK, setMinFrequencyK] = useState(2);

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [comparisonResult, setComparisonResult] = useState<NgramComparisonResponse | null>(null);

  const handleNValueChange = (n: number) => {
    setNgramNValues(prev => 
      prev.includes(n) ? prev.filter(val => val !== n) : [...prev, n].sort()
    );
  };

  const handleCompare = async () => {
    if (!sourceQIdentifier.trim() || !sourceKIdentifier.trim()) {
      setError('比較する2つのソースの情報を入力してください。');
      return;
    }
    if (ngramNValues.length === 0) {
      setError('比較するN-gramの種類（N値）を少なくとも1つ選択してください。');
      return;
    }

    setError('');
    setIsLoading(true);
    setComparisonResult(null);

    const requestPayload: NgramComparisonRequest = {
      source_q: { source_type: sourceQType, identifier: sourceQIdentifier.trim() },
      source_k: { source_type: sourceKType, identifier: sourceKIdentifier.trim() },
      ngram_n_values: ngramNValues,
      step_size: Number(stepSize),
      max_rank: Number(maxRank),
      min_frequency_q: Number(minFrequencyQ),
      min_frequency_k: Number(minFrequencyK),
    };

    const apiUrlBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

    try {
      const response = await fetch(`${apiUrlBase}/analysis/compare/ngrams`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestPayload),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ detail: 'N-gram比較リクエストに失敗しました。'}));
        throw new Error(errData.detail || errData.error_message || '比較処理中にエラーが発生しました。');
      }
      const data: NgramComparisonResponse = await response.json();
      if (data.error_message) {
        setError(data.error_message);
      } else {
        setComparisonResult(data);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'N-gram比較中に不明なエラーが発生しました。');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 py-8">
      <div className="container mx-auto px-4 max-w-5xl">
        <div className="mb-6">
          <Link href="/">
            <Button variant="outline" className="mb-4">
              <ArrowLeft className="mr-2 h-4 w-4" />
              ホームに戻る
            </Button>
          </Link>
          <div className="flex items-center gap-3 mb-4">
            <Repeat className="h-8 w-8" />
            <div>
              <h1 className="text-3xl font-bold text-slate-900">
                N-gram 比較分析
              </h1>
              <p className="text-slate-600">
                2つのデータソース間でN-gramの出現頻度と共通性を比較します。
              </p>
            </div>
          </div>
        </div>

        <Card className="mb-6">
          <CardHeader>
            <CardTitle>比較設定</CardTitle>
            <CardDescription>
              比較したい2つのソースとN-gramのパラメータを設定してください。<br />
              各ソースの識別子には、リポジトリの場合は `owner/repo` 形式またはGitHub URLを、<br />
              ユーザーの場合は `username` 形式またはGitHubプロフィールURLを入力できます。<br />
              分析対象のデータがキャッシュにない場合は、比較実行時に自動的に分析が行われます（時間がかかることがあります）。<br />
              <strong>ステップサイズ</strong>は、比較するランクの範囲を区切る大きさを指定します。例えば最大比較ランクが200の場合、ステップサイズ20なら1-20位、21-40位、...と10個の区間で比較し、ステップサイズ50なら1-50位、51-100位、...と4個の区間で比較します。ステップサイズが小さいほど詳細な分析ができますが結果が多くなり、大きいほど概要を把握しやすくなります。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="grid md:grid-cols-2 gap-6">
              {/* Source Q */}
              <div className="space-y-3 p-4 border rounded-md">
                <h3 className="font-semibold text-lg">ソースQ (比較元)</h3>
                <Select value={sourceQType} onValueChange={setSourceQType}>
                  <SelectTrigger><SelectValue placeholder="タイプ選択" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="repository">リポジトリ</SelectItem>
                    <SelectItem value="user">ユーザー</SelectItem>
                  </SelectContent>
                </Select>
                <Input 
                  placeholder={sourceQType === 'repository' ? 'owner/repo' : 'username'}
                  value={sourceQIdentifier}
                  onChange={(e) => setSourceQIdentifier(e.target.value)}
                />
                <div className="space-y-1">
                  <Label htmlFor="minFreqQ">最小出現頻度 (Q)</Label>
                  <Input id="minFreqQ" type="number" value={minFrequencyQ} onChange={(e) => setMinFrequencyQ(Number(e.target.value))} min={1}/>
                </div>
              </div>
              {/* Source K */}
              <div className="space-y-3 p-4 border rounded-md">
                <h3 className="font-semibold text-lg">ソースK (比較先)</h3>
                <Select value={sourceKType} onValueChange={setSourceKType}>
                  <SelectTrigger><SelectValue placeholder="タイプ選択" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="repository">リポジトリ</SelectItem>
                    <SelectItem value="user">ユーザー</SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  placeholder={sourceKType === 'repository' ? 'owner/repo' : 'username'}
                  value={sourceKIdentifier}
                  onChange={(e) => setSourceKIdentifier(e.target.value)}
                />
                 <div className="space-y-1">
                  <Label htmlFor="minFreqK">最小出現頻度 (K)</Label>
                  <Input id="minFreqK" type="number" value={minFrequencyK} onChange={(e) => setMinFrequencyK(Number(e.target.value))} min={1}/>
                </div>
              </div>
            </div>

            <div className="space-y-3 p-4 border rounded-md">
              <h3 className="font-semibold text-lg">N-gram 設定</h3>
              <div className="flex items-center space-x-4">
                <p className="text-sm font-medium">Nの値 (複数選択可):</p>
                {[1, 2, 3].map(n => (
                  <div key={n} className="flex items-center space-x-2">
                    <Checkbox
                      id={`n-${n}`}
                      checked={ngramNValues.includes(n)}
                      onCheckedChange={() => handleNValueChange(n)}
                    />
                    <Label htmlFor={`n-${n}`}>{n === 1 ? 'Uni (単語)' : n === 2 ? 'Bi (2単語続き)' : 'Tri (3単語続き)'}-gram</Label>
                  </div>
                ))}
              </div>
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <Label htmlFor="stepSize">ステップサイズ (上位N件ごと)</Label>
                  <Input id="stepSize" type="number" value={stepSize} onChange={(e) => setStepSize(Number(e.target.value))} min={1}/>
                  <p className="text-xs text-slate-500 mt-1">例: 20に設定すると、上位1-20位、21-40位...の範囲で比較します。</p>
                </div>
                <div>
                  <Label htmlFor="maxRank">最大比較ランク (上位N件まで)</Label>
                  <Input id="maxRank" type="number" value={maxRank} onChange={(e) => setMaxRank(Number(e.target.value))} min={1}/>
                  <p className="text-xs text-slate-500 mt-1">例: 200に設定すると、最大で上位200位までのN-gramを比較対象とします。</p>
                </div>
              </div>
            </div>
            
            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <Button onClick={handleCompare} disabled={isLoading} size="lg" className="w-full">
              {isLoading ? '比較中...' : '比較実行'}
              <BarChartHorizontalBig className="ml-2 h-5 w-5"/>
            </Button>
          </CardContent>
        </Card>

        {comparisonResult && comparisonResult.results_by_n && (
          <Card>
            <CardHeader>
              <CardTitle>比較結果</CardTitle>
              <CardDescription>
                N-gram ({comparisonResult.request_params.ngram_n_values.join(', ')}-gram) の比較結果。
                ステップサイズ: {comparisonResult.request_params.step_size}, 
                最大ランク: {comparisonResult.request_params.max_rank}
                <br />
                <strong>結果の読み方:</strong>
                <ul className="list-disc pl-5 text-sm text-slate-600 mt-1">
                  <li><strong>ランク範囲:</strong> 各データソース（QおよびK）の全コミットメッセージから抽出されたN-gramを、出現頻度順に並べた際の順位（ランク）の区間です。例えば「1-20」は、各ソースで最も頻出する上位1～20位のN-gram群同士を比較していることを示します。</li>
                  <li><strong>共通N-gram数:</strong> そのランク範囲で両ソースに共通して出現したユニークなN-gramの数です。</li>
                  <li><strong>共通N-gram (上位5件):</strong> 実際に共通したN-gramの例です。</li>
                </ul>
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {Object.entries(comparisonResult.results_by_n).map(([nValue, steps]) => (
                <div key={nValue} className="space-y-4">
                  <h3 className="text-xl font-semibold">{nValue}-gram の比較</h3>
                  {steps.length === 0 ? (
                     <p className="text-slate-500">このN値での比較結果はありませんでした。最小出現頻度やデータを確認してください。</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>ランク範囲</TableHead>
                          <TableHead className="text-center">共通N-gram数</TableHead>
                          <TableHead>共通N-gram (上位5件)</TableHead>
                          {/* <TableHead>ソースQのN-gram</TableHead> */}
                          {/* <TableHead>ソースKのN-gram</TableHead> */}
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {steps.map((step, idx) => (
                          <TableRow key={idx}>
                            <TableCell className="font-medium">{step.rank_start} - {step.rank_end}</TableCell>
                            <TableCell className="text-center text-lg font-bold">{step.common_ngrams_count}</TableCell>
                            <TableCell>
                              {step.common_ngrams.slice(0, 5).join(', ') || '-'}
                              {step.common_ngrams.length > 5 ? '...' : ''}
                            </TableCell>
                            {/* 
                            <TableCell className="text-xs max-w-xs truncate">{step.source_q_ngrams_in_step.join(', ')}</TableCell>
                            <TableCell className="text-xs max-w-xs truncate">{step.source_k_ngrams_in_step.join(', ')}</TableCell>
                            */}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
} 