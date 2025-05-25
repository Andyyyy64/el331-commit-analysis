from fastapi import APIRouter, HTTPException, Depends, Query, Response
from typing import List
import logging
import time # 時間計測用に追加
from datetime import datetime

from ..models.analysis_models import (
    RepositoryRequest, RepositoryResponse, UserRequest, UserAnalysisResponse,
    KwicResponse, NgramResponse, AuthorResponse
)
from ..services.git_service import GitService
from ..services.nlp_service import NLPService

router = APIRouter()
logging.basicConfig(level=logging.INFO) # 基本的なロギング設定
logger = logging.getLogger(__name__)

# サービスのインスタンス
git_service = GitService()
nlp_service = NLPService()

# 分析結果をキャッシュするためのストレージ（実運用ではRedisなどを使用）
analysis_cache = {}

@router.post("/repository", response_model=RepositoryResponse)
async def analyze_repository(request: RepositoryRequest):
    """リポジトリを分析してコミットデータを取得"""
    start_time = time.time() # 処理開始時間
    cache_key = f"{request.owner}/{request.repo}"
    logger.info(f"[分析開始リクエスト] {cache_key}")
    
    try:
        if cache_key in analysis_cache:
            cached_data_time = analysis_cache[cache_key].get('timestamp', '不明')
            logger.info(f"[キャッシュヒット] {cache_key} (最終更新: {cached_data_time})。キャッシュからデータを返却します。")
            return analysis_cache[cache_key]['repository_data']
        
        logger.info(f"[データ取得開始] {cache_key}: GitHub APIからコミットデータを取得します。")
        api_fetch_start_time = time.time()
        commits = await git_service.get_commits_from_github_api(request.owner, request.repo)
        api_fetch_duration = time.time() - api_fetch_start_time
        logger.info(f"[データ取得完了] {cache_key}: {len(commits)}件のコミットを取得しました。(所要時間: {api_fetch_duration:.2f}秒)")
        
        if not commits:
            logger.warning(f"[コミットなし] {cache_key}: コミットが見つかりませんでした。")
            # 空のレスポンスを返すか、エラーにするか検討 (現状は空で続行)

        logger.info(f"[NLP処理開始] {cache_key}: {len(commits)}件のコミットを処理します。")
        nlp_start_time = time.time()
        processed_commits = nlp_service.tokenize_commits(commits)
        nlp_duration = time.time() - nlp_start_time
        logger.info(f"[NLP処理完了] {cache_key}: コミットのトークン化が完了しました。(所要時間: {nlp_duration:.2f}秒)")
        
        response = RepositoryResponse(
            owner=request.owner,
            repo=request.repo,
            commits=[
                {
                    'hash': commit['hash'],
                    'author': commit['author'],
                    'email': commit['email'],
                    'message': commit['message'],
                    'date': commit['date']
                }
                for commit in commits 
            ],
            total_commits=len(commits)
        )
        
        analysis_cache[cache_key] = {
            'repository_data': response,
            'processed_commits': processed_commits,
            'timestamp': datetime.now().isoformat() # キャッシュ更新時刻
        }
        
        total_duration = time.time() - start_time
        logger.info(f"[分析完了] {cache_key}: リポジトリ分析が正常に完了しました。(総所要時間: {total_duration:.2f}秒)")
        return response
        
    except HTTPException as e:
        logger.error(f"[HTTPエラー] {cache_key}: {e.detail} (ステータスコード: {e.status_code})")
        raise e
    except Exception as e:
        total_duration_on_error = time.time() - start_time
        logger.error(f"[サーバーエラー] {cache_key}: リポジトリ分析中にエラーが発生しました。(所要時間: {total_duration_on_error:.2f}秒) エラー: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"リポジトリ分析中にサーバーエラーが発生しました: {str(e)}")

@router.post("/user", response_model=UserAnalysisResponse)
async def analyze_user(request: UserRequest):
    """ユーザーのすべての公開リポジトリを分析してコミットデータを取得"""
    start_time = time.time()
    cache_key = f"user:{request.username}"
    logger.info(f"[ユーザー分析開始] {cache_key}")
    
    try:
        if cache_key in analysis_cache:
            cached_data_time = analysis_cache[cache_key].get('timestamp', '不明')
            logger.info(f"[キャッシュヒット] {cache_key} (最終更新: {cached_data_time})。キャッシュからデータを返却します。")
            return analysis_cache[cache_key]['user_data']
        
        logger.info(f"[データ取得開始] {cache_key}: GitHub APIからユーザーのコミットデータを取得します。")
        api_fetch_start_time = time.time()
        # 並行数を指定してコミットを取得 (例: 10)
        commits, analyzed_repositories, total_repositories = await git_service.get_commits_from_user_repositories(
            request.username, 
            concurrency_limit=10 
        )
        api_fetch_duration = time.time() - api_fetch_start_time
        logger.info(f"[データ取得完了] {cache_key}: {len(commits)}件のコミットを{len(analyzed_repositories)}リポジトリから取得。(総リポジトリ数: {total_repositories}) (所要時間: {api_fetch_duration:.2f}秒)")
        
        if not commits:
            logger.warning(f"[コミットなし] {cache_key}: コミットが見つかりませんでした。")
            # 空のレスポンスを返す
            return UserAnalysisResponse(
                username=request.username,
                repositories=[],
                commits=[],
                total_commits=0,
                total_repositories=total_repositories # ユーザーの総リポジトリ数は返す
            )

        logger.info(f"[NLP処理開始] {cache_key}: {len(commits)}件のコミットを処理します。")
        nlp_start_time = time.time()
        processed_commits = nlp_service.tokenize_commits(commits)
        nlp_duration = time.time() - nlp_start_time
        logger.info(f"[NLP処理完了] {cache_key}: コミットのトークン化が完了しました。(所要時間: {nlp_duration:.2f}秒)")
        
        response = UserAnalysisResponse(
            username=request.username,
            repositories=analyzed_repositories, # GitServiceから返された分析済みリポジトリリストを使用
            commits=[
                {
                    'hash': commit['hash'],
                    'author': commit['author'],
                    'email': commit['email'],
                    'message': commit['message'],
                    'date': commit['date'],
                    'repository': commit.get('repository', '')
                }
                for commit in commits 
            ],
            total_commits=len(commits),
            total_repositories=total_repositories
        )
        
        analysis_cache[cache_key] = {
            'user_data': response,
            'processed_commits': processed_commits,
            'timestamp': datetime.now().isoformat()
        }
        
        total_duration = time.time() - start_time
        logger.info(f"[ユーザー分析完了] {cache_key}: ユーザー分析が正常に完了しました。(総所要時間: {total_duration:.2f}秒)")
        return response
        
    except HTTPException as e:
        logger.error(f"[HTTPエラー] {cache_key}: {e.detail} (ステータスコード: {e.status_code})")
        raise e
    except Exception as e:
        total_duration_on_error = time.time() - start_time
        logger.error(f"[サーバーエラー] {cache_key}: ユーザー分析中にエラーが発生しました。(所要時間: {total_duration_on_error:.2f}秒) エラー: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"ユーザー分析中にサーバーエラーが発生しました: {str(e)}")

@router.get("/user/{username}/kwic", response_model=KwicResponse)
async def user_kwic_search(
    username: str,
    keyword: str = Query(..., description="検索キーワード"),
    search_type: str = Query("token", description="検索タイプ: token, pos, entity"),
    window_size: int = Query(5, description="前後の単語数"),
    sort_type: str = Query("sequential", description="ソート順: sequential, next_token_frequency, next_pos_frequency")
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
    sort_type: str = Query("sequential", description="ソート順: sequential, next_token_frequency, next_pos_frequency")
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