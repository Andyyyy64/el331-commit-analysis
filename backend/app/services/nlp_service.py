import spacy
from typing import List, Dict, Tuple
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
                   search_type: str = 'token', window_size: int = 5) -> List[Dict]:
        logger.info(f"[KWIC検索処理開始] キーワード='{keyword}', タイプ='{search_type}', 対象コミット数={len(processed_commits)}")
        start_time = time.time()
        results = []
        
        for commit in processed_commits:
            doc = commit['doc']
            tokens = [token.text for token in doc]
            
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
                        matches.append(ent.start)
            
            for match_idx in matches:
                left_start = max(0, match_idx - window_size)
                keyword_token_span = 1
                if search_type == 'entity':
                    found_ent = next((ent for ent in doc.ents if ent.start == match_idx and ent.label_ == keyword.upper()), None)
                    if found_ent:
                        keyword_token_span = len(found_ent.text.split())
                
                right_end = min(len(tokens), match_idx + keyword_token_span + window_size)
                
                left_context = ' '.join(tokens[left_start:match_idx])
                matched_tokens = tokens[match_idx : match_idx + keyword_token_span]
                keyword_text = ' '.join(matched_tokens)
                right_context = ' '.join(tokens[match_idx + keyword_token_span : right_end])
                
                results.append({
                    'context': ' '.join(tokens[left_start:right_end]),
                    'keyword': keyword_text,
                    'left': left_context,
                    'right': right_context,
                    'commit_hash': commit['hash'][:8]
                })
        
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