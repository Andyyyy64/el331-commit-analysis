from fastapi import APIRouter, HTTPException, Depends, Query, Response
from typing import List, Dict, Optional
import logging
import time # 時間計測用に追加
from datetime import datetime
import re

from ..models.analysis_models import (
    RepositoryRequest, RepositoryResponse, UserRequest, UserAnalysisResponse,
    KwicResponse, NgramResponse, AuthorResponse,
    NgramComparisonRequest, NgramComparisonResponse, NgramComparisonStepResult
)
from ..services.git_service import GitService
from ..services.nlp_service import NLPService

router = APIRouter()
logging.basicConfig(level=logging.INFO) # 基本的なロギング設定
logger = logging.getLogger(__name__)

# GitHub URL/Identifier Parsing Utilities
def parse_github_identifier(identifier: str, source_type: str) -> Optional[Dict[str, str]]:
    """
    Parses a GitHub identifier (URL or owner/repo, username) into its components.
    For repository: returns {"owner": "...", "repo": "..."}
    For user: returns {"username": "..."}
    Returns None if parsing fails.
    """
    identifier = identifier.strip()
    if source_type == "repository":
        # Try to match owner/repo first
        match_owner_repo = re.match(r"^([^/]+)/([^/]+)$", identifier)
        if match_owner_repo:
            return {"owner": match_owner_repo.group(1), "repo": match_owner_repo.group(2).replace(".git", "")}
        
        # Try to match GitHub URL
        match_url = re.match(r"^(?:https?://)?github\.com/([^/]+)/([^/]+)(?:\.git)?/?$", identifier)
        if match_url:
            return {"owner": match_url.group(1), "repo": match_url.group(2)}
        logger.warning(f"[解析エラー] リポジトリ識別子 '{identifier}' を解析できませんでした。")
        return None
    elif source_type == "user":
        # Try to match username first
        match_username = re.match(r"^([a-zA-Z0-9-]+)$", identifier) # Basic username check
        if match_username:
            return {"username": match_username.group(1)}
            
        # Try to match GitHub URL
        match_url = re.match(r"^(?:https?://)?github\.com/([^/]+)/?$", identifier)
        if match_url:
            # Ensure it's not a repo URL by checking for a second path component
            if '/' not in match_url.group(1) : # A simple check, might need refinement
                 return {"username": match_url.group(1)}
        logger.warning(f"[解析エラー] ユーザー識別子 '{identifier}' を解析できませんでした。")
        return None
    return None

# サービスのインスタンス
git_service = GitService()
nlp_service = NLPService()

# 分析結果をキャッシュするためのストレージ（実運用ではRedisなどを使用）
analysis_cache = {}

# --- Core Analysis Logic --- 
async def _ensure_repository_is_analyzed_and_get_commits(owner: str, repo: str) -> Optional[List[Dict]]:
    """Ensures a repository is analyzed (fetching/processing if not cached) and returns its processed commits."""
    cache_key = f"{owner}/{repo}"
    if cache_key in analysis_cache and 'processed_commits' in analysis_cache[cache_key]:
        logger.info(f"[コア分析取得] {cache_key} はキャッシュ済み。処理済みコミットを返します。")
        return analysis_cache[cache_key]['processed_commits']

    logger.info(f"[コア分析開始] {cache_key}: GitHub APIからコミットデータを取得します。")
    api_fetch_start_time = time.time()
    try:
        commits = await git_service.get_commits_from_github_api(owner, repo)
    except Exception as e:
        logger.error(f"[コア分析エラー] {cache_key} のGitHubデータ取得中にエラー: {e}")
        # HTTPExceptionを発生させるか、Noneを返して呼び出し元で処理するか検討。ここではNoneを返す。
        return None 
    api_fetch_duration = time.time() - api_fetch_start_time
    logger.info(f"[コア分析データ取得完了] {cache_key}: {len(commits)}件のコミットを取得。(所要時間: {api_fetch_duration:.2f}秒)")

    if not commits:
        logger.warning(f"[コア分析コミットなし] {cache_key}: コミットが見つかりませんでした。")
        # 空でも処理を進め、キャッシュには空の結果として残す

    logger.info(f"[コア分析NLP処理開始] {cache_key}: {len(commits)}件のコミットを処理します。")
    nlp_start_time = time.time()
    processed_commits = nlp_service.tokenize_commits(commits)
    nlp_duration = time.time() - nlp_start_time
    logger.info(f"[コア分析NLP処理完了] {cache_key}: コミットのトークン化が完了しました。(所要時間: {nlp_duration:.2f}秒)")
    
    response_data_for_cache = RepositoryResponse(
        owner=owner,
        repo=repo,
        commits=[
            {
                'hash': commit['hash'], 'author': commit['author'], 'email': commit['email'],
                'message': commit['message'], 'date': commit['date']
            }
            for commit in commits
        ],
        total_commits=len(commits)
    )

    analysis_cache[cache_key] = {
        'repository_data': response_data_for_cache,
        'processed_commits': processed_commits,
        'timestamp': datetime.now().isoformat()
    }
    logger.info(f"[コア分析完了] {cache_key}: 分析とキャッシュが完了しました。")
    return processed_commits

async def _ensure_user_is_analyzed_and_get_commits(username: str) -> Optional[List[Dict]]:
    """Ensures a user's repositories are analyzed and returns all their processed commits."""
    cache_key = f"user:{username}"
    if cache_key in analysis_cache and 'processed_commits' in analysis_cache[cache_key]:
        logger.info(f"[コアユーザー分析取得] {cache_key} はキャッシュ済み。処理済みコミットを返します。")
        return analysis_cache[cache_key]['processed_commits']

    logger.info(f"[コアユーザー分析開始] {cache_key}: GitHub APIからユーザーのコミットデータを取得します。")
    api_fetch_start_time = time.time()
    try:
        # concurrency_limit はデフォルト値を使用するか、設定可能にするか検討
        commits, analyzed_repositories, total_repositories = await git_service.get_commits_from_user_repositories(
            username, concurrency_limit=10 
        )
    except Exception as e:
        logger.error(f"[コアユーザー分析エラー] {cache_key} のGitHubデータ取得中にエラー: {e}")
        return None
    api_fetch_duration = time.time() - api_fetch_start_time
    logger.info(f"[コアユーザー分析データ取得完了] {cache_key}: {len(commits)}件を{len(analyzed_repositories)}/{total_repositories}リポジトリから取得。(所要時間: {api_fetch_duration:.2f}秒)")

    if not commits:
        logger.warning(f"[コアユーザー分析コミットなし] {cache_key}: コミットが見つかりませんでした。")
    
    logger.info(f"[コアユーザー分析NLP処理開始] {cache_key}: {len(commits)}件のコミットを処理します。")
    nlp_start_time = time.time()
    processed_commits = nlp_service.tokenize_commits(commits)
    nlp_duration = time.time() - nlp_start_time
    logger.info(f"[コアユーザー分析NLP処理完了] {cache_key}: コミットのトークン化完了。(所要時間: {nlp_duration:.2f}秒)")

    response_data_for_cache = UserAnalysisResponse(
        username=username,
        repositories=analyzed_repositories,
        commits=[
            {
                'hash': commit['hash'], 'author': commit['author'], 'email': commit['email'],
                'message': commit['message'], 'date': commit['date'], 'repository': commit.get('repository', '')
            }
            for commit in commits
        ],
        total_commits=len(commits),
        total_repositories=total_repositories
    )

    analysis_cache[cache_key] = {
        'user_data': response_data_for_cache,
        'processed_commits': processed_commits,
        'timestamp': datetime.now().isoformat()
    }
    logger.info(f"[コアユーザー分析完了] {cache_key}: 分析とキャッシュが完了しました。")
    return processed_commits

@router.post("/repository", response_model=RepositoryResponse)
async def analyze_repository(request: RepositoryRequest):
    """リポジトリを分析してコミットデータを取得"""
    start_time = time.time()
    parsed_identifier = parse_github_identifier(f"{request.owner}/{request.repo}", "repository")
    if not parsed_identifier:
        raise HTTPException(status_code=400, detail=f"無効なリポジトリ識別子: {request.owner}/{request.repo}")
    
    owner, repo = parsed_identifier["owner"], parsed_identifier["repo"]
    cache_key = f"{owner}/{repo}"
    logger.info(f"[分析開始リクエスト] {cache_key}")

    # キャッシュに完全なレスポンスデータがあるか確認 (processed_commitsだけでなくrepository_dataも)
    if cache_key in analysis_cache and 'repository_data' in analysis_cache[cache_key]:
        cached_data_time = analysis_cache[cache_key].get('timestamp', '不明')
        logger.info(f"[キャッシュヒット] {cache_key} (最終更新: {cached_data_time})。キャッシュからデータを返却します。")
        return analysis_cache[cache_key]['repository_data']
        
    processed_commits = await _ensure_repository_is_analyzed_and_get_commits(owner, repo)
    
    if processed_commits is None: # _ensure... 関数内でエラーが発生した場合
        raise HTTPException(status_code=500, detail=f"リポジトリ {owner}/{repo} の分析中にエラーが発生しました。")

    # _ensure... 関数が成功すれば、キャッシュには repository_data も含まれているはず
    if cache_key in analysis_cache and 'repository_data' in analysis_cache[cache_key]:
        total_duration = time.time() - start_time
        logger.info(f"[分析完了] {cache_key}: リポジトリ分析が正常に完了しました。(総所要時間: {total_duration:.2f}秒)")
        return analysis_cache[cache_key]['repository_data']
    else:
        # このケースは通常発生しないはずだが、フォールバック
        logger.error(f"[分析エラー] {cache_key}: 分析後のキャッシュデータが見つかりません。")
        raise HTTPException(status_code=500, detail=f"リポジトリ {owner}/{repo} の分析データ作成に失敗しました。")

@router.post("/user", response_model=UserAnalysisResponse)
async def analyze_user(request: UserRequest):
    """ユーザーのすべての公開リポジトリを分析してコミットデータを取得"""
    start_time = time.time()
    parsed_identifier = parse_github_identifier(request.username, "user")
    if not parsed_identifier:
        raise HTTPException(status_code=400, detail=f"無効なユーザー識別子: {request.username}")

    username = parsed_identifier["username"]
    cache_key = f"user:{username}"
    logger.info(f"[ユーザー分析開始リクエスト] {cache_key}")

    if cache_key in analysis_cache and 'user_data' in analysis_cache[cache_key]:
        cached_data_time = analysis_cache[cache_key].get('timestamp', '不明')
        logger.info(f"[キャッシュヒット] {cache_key} (最終更新: {cached_data_time})。キャッシュからデータを返却します。")
        return analysis_cache[cache_key]['user_data']

    processed_commits = await _ensure_user_is_analyzed_and_get_commits(username)

    if processed_commits is None:
        # ユーザーが見つからない場合やリポジトリがない場合は空の成功レスポンスを返す設計だったが、
        # _ensure_user_is_analyzed_and_get_commits が None を返した場合、何らかのエラーの可能性が高い
        # ただし、元々のGitServiceでは空コミットの場合も空リストを返すので、その場合は processed_commits が空リストになる
        # ここではNoneは明確なエラーケースとして扱う
        raise HTTPException(status_code=500, detail=f"ユーザー {username} の分析中にエラーが発生しました。")
    
    # _ensure... 関数が成功すれば、キャッシュには user_data も含まれているはず
    if cache_key in analysis_cache and 'user_data' in analysis_cache[cache_key]:
        total_duration = time.time() - start_time
        logger.info(f"[ユーザー分析完了] {cache_key}: ユーザー分析が正常に完了しました。(総所要時間: {total_duration:.2f}秒)")
        return analysis_cache[cache_key]['user_data']
    else:
        # ユーザーが全くコミットを持っていない場合、processed_commits は空リストだが、user_dataは作成されるはず。
        # このパスは通常、エラー時のみ。
        logger.error(f"[ユーザー分析エラー] {cache_key}: 分析後のキャッシュデータが見つかりません。")
        # ユーザーが存在しない、またはリポジトリが全くない場合、GitServiceは空のコミットリストを返す。
        # NLPServiceも空の処理済みコミットを返し、キャッシュには total_repositories: 0 のUserAnalysisResponseが入る。
        # もしuser_dataがそれでもないなら問題。
        # 特別ケース: total_repositories: 0 だった場合、空の正しいレスポンスを返す。
        if cache_key in analysis_cache and analysis_cache[cache_key].get('user_data') and \
           analysis_cache[cache_key]['user_data'].total_commits == 0:
            return analysis_cache[cache_key]['user_data']
            
        raise HTTPException(status_code=500, detail=f"ユーザー {username} の分析データ作成に失敗しました。")

@router.get("/user/{username}/kwic", response_model=KwicResponse)
async def user_kwic_search(
    username: str,
    keyword: str = Query(..., description="検索キーワード"),
    search_type: str = Query("token", description="検索タイプ: token, pos, entity"),
    window_size: int = Query(5, description="前後の単語数"),
    sort_type: str = Query("next_token_pos_combination_frequency", description="ソート順: sequential, next_token_frequency, next_pos_frequency, next_token_pos_combination_frequency")
):
    """ユーザー分析でのKWIC検索を実行"""
    start_time = time.time()
    cache_key = f"user:{username}" # Correct cache key format
    logger.info(f"--- DEBUG: user_kwic_search --- START ---")
    logger.info(f"--- DEBUG: Received username: '{username}' (type: {type(username)})" )
    logger.info(f"--- DEBUG: Attempting to use cache_key: '{cache_key}'")
    logger.info(f"--- DEBUG: All available cache keys: {list(analysis_cache.keys())}")
    
    if cache_key not in analysis_cache or 'processed_commits' not in analysis_cache[cache_key]:
        logger.warning(f"[ユーザーKWIC検索エラー] Cache key '{cache_key}' not found or does not contain 'processed_commits'. Available keys: {list(analysis_cache.keys())}")
        raise HTTPException(
            status_code=404, 
            detail=f"ユーザー '{username}' の事前分析データが見つかりません。先にユーザー分析を実行してください。 (Tried key: {cache_key})"
        )
    
    logger.info(f"--- DEBUG: Cache key '{cache_key}' found with 'processed_commits'.")
    logger.info(f"[ユーザーKWIC検索開始] {cache_key}: キーワード='{keyword}', タイプ='{search_type}', ウィンドウサイズ={window_size}, ソート='{sort_type}'")
    
    try:
        processed_commits = analysis_cache[cache_key]['processed_commits']
        results = nlp_service.kwic_search(
            processed_commits, keyword, search_type, window_size, sort_type
        )
        duration = time.time() - start_time
        logger.info(f"[ユーザーKWIC検索完了] {cache_key}: {len(results)}件の結果。(所要時間: {duration:.2f}秒)")
        return KwicResponse(
            keyword=keyword, search_type=search_type, window_size=window_size, results=results,
            sort_type=sort_type
        )
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[ユーザーKWIC検索エラー] {cache_key}: 処理中にエラー。(所要時間: {duration:.2f}秒) エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"KWIC検索に失敗しました: {str(e)}")

@router.get("/user/{username}/ngrams", response_model=NgramResponse)
async def get_user_ngrams(
    username: str,
    n: int = Query(2, description="N-gramのN値"),
    min_frequency: int = Query(2, description="最小出現頻度")
):
    """ユーザー分析でのN-gram分析結果を取得"""
    start_time = time.time()
    cache_key = f"user:{username}" # Correct cache key format
    logger.info(f"--- DEBUG: get_user_ngrams --- START ---")
    logger.info(f"--- DEBUG: Received username: '{username}' (type: {type(username)})" )
    logger.info(f"--- DEBUG: Attempting to use cache_key: '{cache_key}'")
    logger.info(f"--- DEBUG: All available cache keys: {list(analysis_cache.keys())}")

    if cache_key not in analysis_cache or 'processed_commits' not in analysis_cache[cache_key]:
        logger.warning(f"[ユーザーN-gram分析エラー] Cache key '{cache_key}' not found or does not contain 'processed_commits'. Available keys: {list(analysis_cache.keys())}")
        raise HTTPException(
            status_code=404, 
            detail=f"ユーザー '{username}' の事前分析データが見つかりません。先にユーザー分析を実行してください。 (Tried key: {cache_key})"
        )
    
    logger.info(f"--- DEBUG: Cache key '{cache_key}' found with 'processed_commits'.")
    logger.info(f"[ユーザーN-gram分析開始] {cache_key}: N={n}, 最小頻度={min_frequency}")

    try:
        processed_commits = analysis_cache[cache_key]['processed_commits']
        ngrams = nlp_service.generate_ngrams(processed_commits, n=n, min_frequency=min_frequency)
        duration = time.time() - start_time
        logger.info(f"[ユーザーN-gram分析完了] {cache_key}: {len(ngrams)}種類のN-gramを生成。(所要時間: {duration:.2f}秒)")
        return NgramResponse(ngrams=ngrams, total_ngrams=len(ngrams))
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[ユーザーN-gram分析エラー] {cache_key}: 処理中にエラー。(所要時間: {duration:.2f}秒) エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"ユーザーN-gram分析に失敗しました: {str(e)}")

@router.get("/user/{username}/authors", response_model=AuthorResponse)
async def get_user_author_analysis(username: str):
    """ユーザー分析での著者分析結果を取得"""
    start_time = time.time()
    cache_key = f"user:{username}" # Correct cache key format
    logger.info(f"--- DEBUG: get_user_author_analysis --- START ---")
    logger.info(f"--- DEBUG: Received username: '{username}' (type: {type(username)})" )
    logger.info(f"--- DEBUG: Attempting to use cache_key: '{cache_key}'")
    logger.info(f"--- DEBUG: All available cache keys: {list(analysis_cache.keys())}")

    if cache_key not in analysis_cache or 'processed_commits' not in analysis_cache[cache_key]:
        logger.warning(f"[ユーザー著者分析エラー] Cache key '{cache_key}' not found or does not contain 'processed_commits'. Available keys: {list(analysis_cache.keys())}")
        raise HTTPException(
            status_code=404, 
            detail=f"ユーザー '{username}' の事前分析データが見つかりません。先にユーザー分析を実行してください。 (Tried key: {cache_key})"
        )
    
    logger.info(f"--- DEBUG: Cache key '{cache_key}' found with 'processed_commits'.")
    logger.info(f"[ユーザー著者分析開始] {cache_key}")

    try:
        processed_commits = analysis_cache[cache_key]['processed_commits']
        authors = nlp_service.analyze_authors(processed_commits)
        duration = time.time() - start_time
        logger.info(f"[ユーザー著者分析完了] {cache_key}: {len(authors)}人の著者を分析。(所要時間: {duration:.2f}秒)")
        return AuthorResponse(authors=authors, total_authors=len(authors))
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[ユーザー著者分析エラー] {cache_key}: 処理中にエラー。(所要時間: {duration:.2f}秒) エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"著者分析に失敗しました: {str(e)}")

@router.get("/{owner}/{repo}/kwic", response_model=KwicResponse)
async def kwic_search(
    owner: str, 
    repo: str,
    keyword: str = Query(..., description="検索キーワード"),
    search_type: str = Query("token", description="検索タイプ: token, pos, entity"),
    window_size: int = Query(5, description="前後の単語数"),
    sort_type: str = Query("next_token_pos_combination_frequency", description="ソート順: sequential, next_token_frequency, next_pos_frequency, next_token_pos_combination_frequency")
):
    """KWIC検索を実行"""
    start_time = time.time()
    cache_key = f"{owner}/{repo}"
    logger.info(f"[KWIC検索開始] {cache_key}: キーワード='{keyword}', タイプ='{search_type}', ウィンドウサイズ={window_size}, ソート='{sort_type}'")
    
    if cache_key not in analysis_cache or 'processed_commits' not in analysis_cache[cache_key]:
        logger.warning(f"[KWIC検索エラー] {cache_key}: 事前分析データが見つかりません。先にリポジトリ分析を実行してください。")
        raise HTTPException(
            status_code=404, 
            detail="リポジトリが分析されていません。先にリポジトリ分析を実行してください。"
        )
    
    try:
        processed_commits = analysis_cache[cache_key]['processed_commits']
        results = nlp_service.kwic_search(
            processed_commits, keyword, search_type, window_size, sort_type
        )
        duration = time.time() - start_time
        logger.info(f"[KWIC検索完了] {cache_key}: {len(results)}件の結果。(所要時間: {duration:.2f}秒)")
        return KwicResponse(
            keyword=keyword, search_type=search_type, window_size=window_size, results=results,
            sort_type=sort_type
        )
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[KWIC検索エラー] {cache_key}: 処理中にエラー。(所要時間: {duration:.2f}秒) エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"KWIC検索に失敗しました: {str(e)}")

@router.get("/{owner}/{repo}/ngrams", response_model=NgramResponse)
async def get_ngrams(
    owner: str, 
    repo: str,
    n: int = Query(2, description="N-gramのN値"),
    min_frequency: int = Query(2, description="最小出現頻度")
):
    """N-gram分析結果を取得"""
    start_time = time.time()
    cache_key = f"{owner}/{repo}"
    logger.info(f"[N-gram分析開始] {cache_key}: N={n}, 最小頻度={min_frequency}")

    if cache_key not in analysis_cache or 'processed_commits' not in analysis_cache[cache_key]:
        logger.warning(f"[N-gram分析エラー] {cache_key}: 事前分析データが見つかりません。先にリポジトリ分析を実行してください。")
        raise HTTPException(
            status_code=404, 
            detail="リポジトリが分析されていません。先にリポジトリ分析を実行してください。"
        )
    
    try:
        processed_commits = analysis_cache[cache_key]['processed_commits']
        ngrams = nlp_service.generate_ngrams(processed_commits, n=n, min_frequency=min_frequency)
        duration = time.time() - start_time
        logger.info(f"[N-gram分析完了] {cache_key}: {len(ngrams)}種類のN-gramを生成。(所要時間: {duration:.2f}秒)")
        return NgramResponse(ngrams=ngrams, total_ngrams=len(ngrams))
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[N-gram分析エラー] {cache_key}: 処理中にエラー。(所要時間: {duration:.2f}秒) エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"N-gram分析に失敗しました: {str(e)}")

@router.get("/{owner}/{repo}/authors", response_model=AuthorResponse)
async def get_author_analysis(owner: str, repo: str):
    """著者分析結果を取得"""
    start_time = time.time()
    cache_key = f"{owner}/{repo}"
    logger.info(f"[著者分析開始] {cache_key}")

    if cache_key not in analysis_cache or 'processed_commits' not in analysis_cache[cache_key]:
        logger.warning(f"[著者分析エラー] {cache_key}: 事前分析データが見つかりません。先にリポジトリ分析を実行してください。")
        raise HTTPException(
            status_code=404, 
            detail="リポジトリが分析されていません。先にリポジトリ分析を実行してください。"
        )
    
    try:
        processed_commits = analysis_cache[cache_key]['processed_commits']
        authors = nlp_service.analyze_authors(processed_commits)
        duration = time.time() - start_time
        logger.info(f"[著者分析完了] {cache_key}: {len(authors)}人の著者を分析。(所要時間: {duration:.2f}秒)")
        return AuthorResponse(authors=authors, total_authors=len(authors))
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[著者分析エラー] {cache_key}: 処理中にエラー。(所要時間: {duration:.2f}秒) エラー: {str(e)}")
        raise HTTPException(status_code=500, detail=f"著者分析に失敗しました: {str(e)}")

@router.delete("/{owner}/{repo}/cache")
async def clear_cache(owner: str, repo: str):
    """キャッシュをクリア"""
    cache_key = f"{owner}/{repo}"
    logger.info(f"[キャッシュクリアリクエスト] {cache_key}")
    
    if cache_key in analysis_cache:
        del analysis_cache[cache_key]
        logger.info(f"[キャッシュクリア完了] {cache_key}")
        return {"message": f"キャッシュをクリアしました: {cache_key}"}
    else:
        logger.warning(f"[キャッシュクリア失敗] {cache_key}: キャッシュが見つかりません。")
        raise HTTPException(status_code=404, detail="キャッシュが見つかりません")

@router.delete("/user/{username}/cache")
async def clear_user_cache(username: str):
    """ユーザーキャッシュをクリア"""
    cache_key = f"user:{username}"
    logger.info(f"[ユーザーキャッシュクリアリクエスト] {cache_key}")
    
    if cache_key in analysis_cache:
        del analysis_cache[cache_key]
        logger.info(f"[ユーザーキャッシュクリア完了] {cache_key}")
        return {"message": f"ユーザーキャッシュをクリアしました: {cache_key}"}
    else:
        logger.warning(f"[ユーザーキャッシュクリア失敗] {cache_key}: キャッシュが見つかりません。")
        raise HTTPException(status_code=404, detail="ユーザーキャッシュが見つかりません")

@router.get("/debug/cache")
async def debug_cache():
    """デバッグ用: 現在のキャッシュ状況を表示"""
    cache_keys = list(analysis_cache.keys())
    cache_info = {}
    for key in cache_keys:
        cache_data = analysis_cache[key]
        cache_info[key] = {
            "has_processed_commits": "processed_commits" in cache_data,
            "timestamp": cache_data.get("timestamp", "不明"),
            "data_type": "user_data" if "user_data" in cache_data else "repository_data" if "repository_data" in cache_data else "unknown"
        }
    
    return {
        "total_cache_entries": len(cache_keys),
        "cache_keys": cache_keys,
        "cache_details": cache_info
    }

@router.post("/compare/ngrams", response_model=NgramComparisonResponse)
async def compare_ngrams_endpoint(request: NgramComparisonRequest):
    logger.info(f"[N-gram比較APIリクエスト受信] Q: {request.source_q.identifier}, K: {request.source_k.identifier}")
    start_time = time.time()

    async def get_processed_commits(source_type: str, identifier: str) -> Optional[List[Dict]]:
        cache_key_prefix = "user:" if source_type == "user" else ""
        cache_key = f"{cache_key_prefix}{identifier}"
        
        # 以前はここでキャッシュがなければエラーだったが、これからは自動分析を試みる
        parsed_id = parse_github_identifier(identifier, source_type)
        if not parsed_id:
            logger.error(f"[N-gram比較自動分析エラー] 識別子を解析できませんでした: {identifier}")
            return None

        if source_type == "user":
            return await _ensure_user_is_analyzed_and_get_commits(parsed_id["username"])
        elif source_type == "repository":
            return await _ensure_repository_is_analyzed_and_get_commits(parsed_id["owner"], parsed_id["repo"])
        return None

    processed_commits_q = await get_processed_commits(request.source_q.source_type, request.source_q.identifier)
    processed_commits_k = await get_processed_commits(request.source_k.source_type, request.source_k.identifier)

    if not processed_commits_q:
        return NgramComparisonResponse(
            request_params=request,
            results_by_n={},
            error_message=f"ソースQ ({request.source_q.identifier}) の分析データが見つかりません。先に分析を実行してください。"
        )
    if not processed_commits_k:
        return NgramComparisonResponse(
            request_params=request,
            results_by_n={},
            error_message=f"ソースK ({request.source_k.identifier}) の分析データが見つかりません。先に分析を実行してください。"
        )
    
    logger.info(f"  データQ: {len(processed_commits_q)}件の処理済みコミット, データK: {len(processed_commits_k)}件の処理済みコミット")

    try:
        comparison_results = nlp_service.compare_ngrams_stepwise(
            processed_commits_q=processed_commits_q,
            processed_commits_k=processed_commits_k,
            ngram_n_values=request.ngram_n_values,
            step_size=request.step_size,
            max_rank=request.max_rank,
            min_frequency_q=request.min_frequency_q,
            min_frequency_k=request.min_frequency_k
        )
        duration = time.time() - start_time
        logger.info(f"[N-gram比較API処理完了] 所要時間: {duration:.2f}秒")
        
        # NgramComparisonStepResultモデルに適合するように変換 (もし必要なら)
        # 現在のcompare_ngrams_stepwiseはDictを返すので、それをそのまま利用
        # results_by_n_typed: Dict[int, List[NgramComparisonStepResult]] = {}
        # for n, steps in comparison_results.items():
        #     results_by_n_typed[n] = [NgramComparisonStepResult(**step) for step in steps]

        return NgramComparisonResponse(
            request_params=request, 
            results_by_n=comparison_results # nlp_serviceが返すDict[int, List[Dict]]をそのまま利用
        )

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[N-gram比較APIエラー] 処理中にエラー。(所要時間: {duration:.2f}秒) エラー: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return NgramComparisonResponse(
            request_params=request,
            results_by_n={},
            error_message=f"N-gram比較中にサーバーエラーが発生しました: {str(e)}"
        ) 