import spacy
from typing import List, Dict, Tuple, Optional
from collections import Counter, defaultdict
import re
import logging # ロギング追加
import time    # 時間計測用に追加

logger = logging.getLogger(__name__) # ロガーインスタンス作成

class NLPService:
    def __init__(self):
        logger.info("[NLPService初期化] spaCyモデルをロード中...")
        load_start_time = time.time()
        try:
            self.nlp = spacy.load("en_core_web_sm")
            load_duration = time.time() - load_start_time
            logger.info(f"[NLPService初期化] spaCyモデルロード完了。(所要時間: {load_duration:.2f}秒)")
        except OSError as e:
            logger.error(f"[NLPService初期化エラー] spaCy英語モデル(en_core_web_sm)のロードに失敗しました: {e}")
            raise Exception("spaCy英語モデル(en_core_web_sm)が見つかりません。`python -m spacy download en_core_web_sm`で インストールしてください。")

    def preprocess_text(self, text: str) -> str:
        """テキストの前処理"""
        # 改行やタブを空白に変換
        text = re.sub(r'\s+', ' ', text)
        # 特殊文字の正規化
        text = text.strip()
        return text

    def tokenize_commits(self, commits: List[Dict]) -> List[Dict]:
        logger.info(f"[トークン化開始] {len(commits)}件のコミットメッセージを処理します。")
        start_time = time.time()
        processed_commits = []
        
        for i, commit in enumerate(commits):
            if (i + 1) % 100 == 0:
                current_duration = time.time() - start_time
                logger.info(f"[トークン化進捗] {i + 1}/{len(commits)}件処理完了。(経過時間: {current_duration:.2f}秒)")

            message = self.preprocess_text(commit['message'])
            doc = self.nlp(message)
            
            tokens = []
            for token in doc:
                tokens.append({
                    'text': token.text,
                    'lemma': token.lemma_,
                    'pos': token.pos_,
                    'tag': token.tag_,
                    'is_alpha': token.is_alpha,
                    'is_stop': token.is_stop
                })
            
            processed_commits.append({
                **commit,
                'processed_message': message,
                'tokens': tokens,
                'doc': doc  # spaCyのDocオブジェクトも保持
            })
        
        total_duration = time.time() - start_time
        logger.info(f"[トークン化完了] 全{len(commits)}件のコミットメッセージ処理完了。(総所要時間: {total_duration:.2f}秒)")
        return processed_commits

    def kwic_search(self, processed_commits: List[Dict], keyword: str, 
                   search_type: str = 'token', window_size: int = 5,
                   sort_type: str = 'sequential') -> List[Dict]:
        logger.info(f"[KWIC検索処理開始] キーワード='{keyword}', タイプ='{search_type}', ソート='{sort_type}', 対象コミット数={len(processed_commits)}")
        start_time = time.time()
        results = []
        
        for commit in processed_commits:
            doc = commit['doc']
            # tokens = [token.text for token in doc] # spaCy v3ではdoc.textで取得したほうが良い場合があるが、ここではtoken objectを使う
            
            matches = []
            if search_type == 'token':
                matches = [i for i, token_obj in enumerate(doc) 
                          if token_obj.text.lower() == keyword.lower()]
            elif search_type == 'pos':
                matches = [i for i, token_obj in enumerate(doc) 
                          if token_obj.pos_ == keyword.upper()]
            elif search_type == 'entity':
                for ent in doc.ents:
                    if ent.label_ == keyword.upper():
                        # エンティティの場合、エンティティの開始トークンのインデックスをmatchとする
                        matches.append(ent.start)
            
            for match_idx in matches:
                left_start = max(0, match_idx - window_size)
                
                # キーワード自体のトークン（単数または複数）を特定
                keyword_tokens_text = []
                keyword_start_index = match_idx
                keyword_end_index = match_idx + 1 # デフォルトは1トークン

                if search_type == 'entity':
                    found_ent = next((ent for ent in doc.ents if ent.start == match_idx and ent.label_ == keyword.upper()), None)
                    if found_ent:
                        keyword_tokens_text = [token.text for token in found_ent]
                        keyword_end_index = found_ent.end
                    else: # Entityが見つからない場合は、マッチしたトークン自体をキーワードとする(通常ありえないがフォールバック)
                        keyword_tokens_text = [doc[match_idx].text]
                elif search_type == 'pos': # 品詞の場合、マッチしたトークン自体をキーワードとする
                    keyword_tokens_text = [doc[match_idx].text]
                else: # token検索の場合
                    keyword_tokens_text = [doc[match_idx].text] # keyword.lower()で検索しているので、元のテキストを使う
                
                actual_keyword_text = ' '.join(keyword_tokens_text)

                # キーワードの直後のトークンとその品詞を取得
                next_token_text = None
                next_token_pos = None
                if keyword_end_index < len(doc):
                    next_token_text = doc[keyword_end_index].text.lower()
                    next_token_pos = doc[keyword_end_index].pos_

                right_context_start = keyword_end_index
                right_context_end = min(len(doc), keyword_end_index + window_size)
                
                left_context = ' '.join([t.text for t in doc[left_start:keyword_start_index]])
                right_context = ' '.join([t.text for t in doc[right_context_start:right_context_end]])
                
                results.append({
                    'context': ' '.join([t.text for t in doc[left_start:right_context_end]]),
                    'keyword': actual_keyword_text,
                    'left': left_context,
                    'right': right_context,
                    'commit_hash': commit['hash'][:8],
                    'next_token': next_token_text, 
                    'next_pos': next_token_pos,
                    'sort_metric_label': None, # Will be set after sorting
                    'sort_metric_value': None  # Will be set after sorting
                })
        
        # ソート処理とメトリック値の設定
        if sort_type == 'next_token_frequency' and results:
            next_token_counts = Counter(r['next_token'] for r in results if r['next_token'])
            results.sort(key=lambda x: next_token_counts[x['next_token']] if x['next_token'] else 0, reverse=True)
            for r in results:
                if r['next_token']:
                    r['sort_metric_label'] = "後続単語頻度"
                    r['sort_metric_value'] = f"{r['next_token']} ({next_token_counts[r['next_token']]}回)"
                else:
                    r['sort_metric_label'] = "後続単語なし"
                    r['sort_metric_value'] = "-"
        elif sort_type == 'next_pos_frequency' and results:
            next_pos_counts = Counter(r['next_pos'] for r in results if r['next_pos'])
            results.sort(key=lambda x: next_pos_counts[x['next_pos']] if x['next_pos'] else 0, reverse=True)
            for r in results:
                if r['next_pos']:
                    r['sort_metric_label'] = "後続品詞頻度"
                    r['sort_metric_value'] = f"{r['next_pos']} ({next_pos_counts[r['next_pos']]}回)"
                else:
                    r['sort_metric_label'] = "後続品詞なし"
                    r['sort_metric_value'] = "-"
        elif sort_type == 'next_token_pos_combination_frequency' and results:
            next_token_pos_combinations = Counter(
                (r['next_token'], r['next_pos']) for r in results if r['next_token'] and r['next_pos']
            )
            results.sort(
                key=lambda x: next_token_pos_combinations[(x['next_token'], x['next_pos'])]
                if x['next_token'] and x['next_pos'] else 0,
                reverse=True
            )
            for r in results:
                if r['next_token'] and r['next_pos']:
                    combination_key = (r['next_token'], r['next_pos'])
                    count = next_token_pos_combinations[combination_key]
                    r['sort_metric_label'] = "後続トークン・品詞頻度"
                    r['sort_metric_value'] = f"{r['next_token']} ({r['next_pos']}) - {count}回"
                elif r['next_token']: # 品詞がない場合（通常は稀）
                    r['sort_metric_label'] = "後続トークン (品詞なし)"
                    r['sort_metric_value'] = f"{r['next_token']}"
                else:
                    r['sort_metric_label'] = "後続要素なし"
                    r['sort_metric_value'] = "-"
        elif sort_type == 'sequential':
             for r in results:
                r['sort_metric_label'] = "出現順"
                r['sort_metric_value'] = f"(コミット内 {results.index(r) + 1}番目)" # 単純なインデックス
        
        total_duration = time.time() - start_time
        logger.info(f"[KWIC検索処理完了] {len(results)}件の結果。(所要時間: {total_duration:.2f}秒)")
        return results

    def generate_ngrams(self, processed_commits: List[Dict], n: int = 2, 
                       min_frequency: int = 2) -> List[Dict]:
        logger.info(f"[N-gram生成開始] N={n}, 最小頻度={min_frequency}, 対象コミット数={len(processed_commits)}")
        start_time = time.time()
        all_ngrams_list = []
        
        for commit in processed_commits:
            tokens = [token.text.lower() for token in commit['doc'] 
                     if token.is_alpha and not token.is_stop]
            
            for i in range(len(tokens) - n + 1):
                ngram_tuple = tuple(tokens[i:i+n])
                all_ngrams_list.append(' '.join(ngram_tuple))
        
        ngram_counts = Counter(all_ngrams_list)
        result = []
        for rank, (ngram_str, frequency) in enumerate(ngram_counts.most_common(), 1):
            if frequency >= min_frequency:
                result.append({
                    'ngram': ngram_str,
                    'frequency': frequency,
                    'rank': rank
                })
        
        total_duration = time.time() - start_time
        logger.info(f"[N-gram生成完了] {len(result)}種類のN-gramを生成。(所要時間: {total_duration:.2f}秒)")
        return result

    def analyze_authors(self, processed_commits: List[Dict]) -> List[Dict]:
        logger.info(f"[著者分析開始] 対象コミット数={len(processed_commits)}")
        start_time = time.time()
        author_stats = defaultdict(lambda: {
            'commit_count': 0,
            'total_chars': 0,
            'words': [],
            'emails': set()
        })
        
        for commit in processed_commits:
            author = commit['author']
            author_stats[author]['commit_count'] += 1
            author_stats[author]['total_chars'] += len(commit['message'])
            author_stats[author]['emails'].add(commit['email'])
            
            words = [token.text.lower() for token in commit['doc'] 
                    if token.is_alpha and not token.is_stop]
            author_stats[author]['words'].extend(words)
        
        results = []
        for author_name_key, stats in author_stats.items():
            if stats['commit_count'] == 0: continue
            avg_length = stats['total_chars'] / stats['commit_count']
            word_counts = Counter(stats['words'])
            common_words = [word for word, count in word_counts.most_common(20)]
            
            results.append({
                'author': author_name_key,
                'email': list(stats['emails'])[0] if stats['emails'] else '',
                'commit_count': stats['commit_count'],
                'avg_message_length': avg_length,
                'common_words': common_words,
                'total_chars': stats['total_chars']
            })
        
        results.sort(key=lambda x: x['commit_count'], reverse=True)

        total_duration = time.time() - start_time
        logger.info(f"[著者分析完了] {len(results)}人の著者を分析。(所要時間: {total_duration:.2f}秒)")
        return results

    def compare_ngrams_stepwise(
        self,
        processed_commits_q: List[Dict],
        processed_commits_k: List[Dict],
        ngram_n_values: List[int],
        step_size: int,
        max_rank: int,
        min_frequency_q: int,
        min_frequency_k: int
    ) -> Dict[int, List[Dict]]: # Returns a Dict where key is N, value is list of step results
        logger.info(f"[N-gram比較開始] N値: {ngram_n_values}, ステップ: {step_size}, 最大ランク: {max_rank}")
        comparison_results_by_n: Dict[int, List[Dict]] = defaultdict(list)

        for n_val in ngram_n_values:
            logger.info(f"  [N={n_val}] データセットQのN-gramを生成中...")
            ngrams_q_all = self.generate_ngrams(processed_commits_q, n=n_val, min_frequency=min_frequency_q)
            logger.info(f"  [N={n_val}] データセットKのN-gramを生成中...")
            ngrams_k_all = self.generate_ngrams(processed_commits_k, n=n_val, min_frequency=min_frequency_k)

            # N-gram文字列のリストに変換 (ランク順になっているはず)
            ranked_ngrams_q = [item['ngram'] for item in ngrams_q_all]
            ranked_ngrams_k = [item['ngram'] for item in ngrams_k_all]

            logger.info(f"  [N={n_val}] Q: {len(ranked_ngrams_q)}種類, K: {len(ranked_ngrams_k)}種類のN-gramを比較します。")

            for current_rank_start in range(0, min(max_rank, max(len(ranked_ngrams_q), len(ranked_ngrams_k))), step_size):
                rank_end = current_rank_start + step_size

                ngrams_q_step = ranked_ngrams_q[current_rank_start:rank_end]
                ngrams_k_step = ranked_ngrams_k[current_rank_start:rank_end]

                # 共通N-gramを見つける (効率のためセットを使用)
                common_in_step = list(set(ngrams_q_step) & set(ngrams_k_step))
                common_in_step.sort() # 表示順を安定させるためソート

                step_result = {
                    'ngram_n': n_val,
                    'rank_start': current_rank_start + 1, # 1-indexed for display
                    'rank_end': rank_end,
                    'common_ngrams': common_in_step,
                    'common_ngrams_count': len(common_in_step),
                    'source_q_ngrams_in_step': ngrams_q_step,
                    'source_k_ngrams_in_step': ngrams_k_step,
                }
                comparison_results_by_n[n_val].append(step_result)
            
            logger.info(f"  [N={n_val}] 比較ステップ完了。 {len(comparison_results_by_n[n_val])} ステップの結果を生成。")

        logger.info(f"[N-gram比較完了] 全N値の処理完了。")
        return dict(comparison_results_by_n) 