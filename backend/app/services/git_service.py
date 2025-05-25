import requests
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import os
import logging
import asyncio

from ..core.config import settings

logger = logging.getLogger(__name__)

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
RATE_LIMIT_THRESHOLD = 50  # 残りリクエスト数がこの値を下回ったら待機
RATE_LIMIT_BUFFER_SECONDS = 10 # リセット時間までの待機に加えるバッファ秒数

class GitService:
    def __init__(self):
        self.github_pat = settings.GITHUB_PAT
        if not self.github_pat:
            logger.warning("GITHUB_PATが設定されていません。GitHub APIのレートリミットに影響する可能性があります。")

    def _make_graphql_request(self, query: str, variables: Optional[Dict] = None) -> Dict:
        headers = {
            "Authorization": f"bearer {self.github_pat}",
            "Content-Type": "application/json",
        }
        json_payload = {"query": query}
        if variables:
            json_payload["variables"] = variables

        response = requests.post(GITHUB_GRAPHQL_URL, headers=headers, json=json_payload)
        response.raise_for_status() # エラーがあればHTTPErrorを発生させる
        return response.json()

    async def _check_and_handle_rate_limit(self) -> None:
        if not self.github_pat: # PATがない場合はレートリミットチェック不可
            return

        query = "query { rateLimit { limit remaining resetAt } }"
        try:
            data = self._make_graphql_request(query)
            rate_limit_info = data.get("data", {}).get("rateLimit")
            if not rate_limit_info:
                logger.warning("レートリミット情報の取得に失敗しました。")
                return

            remaining = rate_limit_info.get("remaining", float('inf'))
            reset_at_str = rate_limit_info.get("resetAt")
            
            logger.info(f"[RateLimit Check] remaining: {remaining}/{rate_limit_info.get('limit', 'N/A')}")

            if remaining <= RATE_LIMIT_THRESHOLD and reset_at_str:
                reset_at_dt = datetime.fromisoformat(reset_at_str.replace("Z", "+00:00"))
                now_dt = datetime.utcnow()
                
                # UTCタイムゾーン情報を付加 (datetime.utcnow()はnaiveなため)
                reset_at_dt = reset_at_dt.replace(tzinfo=datetime.timezone.utc)
                now_dt = now_dt.replace(tzinfo=datetime.timezone.utc)

                wait_seconds = (reset_at_dt - now_dt).total_seconds() + RATE_LIMIT_BUFFER_SECONDS
                wait_seconds = max(0, wait_seconds) # 念のため負にならないように

                if wait_seconds > 0:
                    logger.warning(f"[RateLimit Check] 残りリクエスト ({remaining}) が少ないため、約{int(wait_seconds)}秒待機します...")
                    time.sleep(wait_seconds)
                    logger.info("[RateLimit Check] 待機完了。リクエストを再開します。")
        except requests.exceptions.RequestException as e:
            logger.error(f"[RateLimit Check] APIリクエストエラー: {e}")
        except Exception as e:
            logger.error(f"[RateLimit Check] レートリミット処理中に予期せぬエラー: {e}")

    async def get_user_repositories(self, username: str, max_repos: int = 100) -> List[Dict]:
        """指定したユーザーのすべての公開リポジトリを取得する"""
        repositories = []
        has_next_page = True
        end_cursor: Optional[str] = None
        repos_fetched = 0

        query_template = """
        query GetUserRepositories($username: String!, $num: Int!, $cursor: String) {
          user(login: $username) {
            repositories(first: $num, after: $cursor, privacy: PUBLIC, orderBy: {field: UPDATED_AT, direction: DESC}) {
              pageInfo {
                hasNextPage
                endCursor
              }
              nodes {
                name
                owner {
                  login
                }
                updatedAt
                primaryLanguage {
                  name
                }
                stargazerCount
                forkCount
                isEmpty
                isArchived
                isDisabled
                isFork
              }
            }
          }
          rateLimit { limit remaining resetAt }
        }
        """

        logger.info(f"[ユーザーリポジトリ取得] {username} のリポジトリを取得開始")

        while has_next_page and repos_fetched < max_repos:
            await self._check_and_handle_rate_limit()

            num_to_fetch = min(100, max_repos - repos_fetched)
            variables = {
                "username": username,
                "num": num_to_fetch,
                "cursor": end_cursor
            }

            try:
                response_data = self._make_graphql_request(query_template, variables)
                if "errors" in response_data:
                    logger.error(f"GraphQLエラー: {response_data['errors']}")
                    raise Exception(f"GraphQLエラー: {response_data['errors']}")

                user_info = response_data.get("data", {}).get("user")
                if not user_info:
                    logger.warning(f"ユーザー {username} が見つかりません。")
                    break

                repo_info = user_info.get("repositories")
                if not repo_info:
                    logger.info(f"ユーザー {username} のリポジトリが見つかりません。")
                    break

                for node in repo_info.get("nodes", []):
                    if repos_fetched >= max_repos:
                        break
                    
                    # 空のリポジトリ、アーカイブ済み、無効、フォークを除外
                    if node.get("isEmpty") or node.get("isArchived") or node.get("isDisabled") or node.get("isFork"):
                        logger.info(f"[リポジトリスキップ] {username}/{node.get('name')}: 空、アーカイブ、無効、またはフォークのためスキップ")
                        continue
                    
                    repositories.append({
                        "name": node.get("name"),
                        "owner": node.get("owner", {}).get("login"),
                        "updated_at": node.get("updatedAt"),
                        "language": node.get("primaryLanguage", {}).get("name") if node.get("primaryLanguage") else None,
                        "stars": node.get("stargazerCount", 0),
                        "forks": node.get("forkCount", 0),
                        "is_fork": node.get("isFork", False)
                    })
                    repos_fetched += 1

                page_info = repo_info.get("pageInfo", {})
                has_next_page = page_info.get("hasNextPage", False)
                end_cursor = page_info.get("endCursor")

                logger.info(f"[ユーザーリポジトリ取得] {username}: {repos_fetched}件のリポジトリを取得。次のページ: {has_next_page}")

            except requests.exceptions.RequestException as e:
                logger.error(f"GitHub APIリクエストエラー: {e}")
                raise Exception(f"GitHub APIリクエストエラー: {e}")
            except Exception as e:
                logger.error(f"リポジトリ取得中に予期せぬエラー: {e}")
                raise Exception(f"リポジトリ取得中に予期せぬエラー: {e}")

        logger.info(f"[ユーザーリポジトリ取得完了] {username}: 合計{len(repositories)}件のリポジトリを取得")
        return repositories

    async def get_commits_from_user_repositories(
        self, username: str, 
        max_commits_per_repo: int = 100, 
        max_total_commits: int = 5000,
        concurrency_limit: int = 5
    ) -> Tuple[List[Dict], List[str], int]:
        """ユーザーのすべての公開リポジトリからコミットを収集する (並行処理版)"""
        
        logger.info(f"[ユーザーコミット分析開始] {username}: 最大{max_total_commits}件のコミットを収集 (並行数: {concurrency_limit})")
        
        repositories = await self.get_user_repositories(username)
        if not repositories:
            logger.warning(f"ユーザー {username} の公開リポジトリが見つかりません。")
            return [], [], 0

        all_commits_data = [] 
        analyzed_repos_names = [] 
        
        semaphore = asyncio.Semaphore(concurrency_limit)
        
        async def _fetch_and_process_repo_commits(repo_info: Dict) -> Optional[List[Dict]]:
            repo_owner = repo_info["owner"]
            repo_name = repo_info["name"]
            repo_full_name = f"{repo_owner}/{repo_name}"

            async with semaphore:
                # logger.info(f"[リポジトリ分析開始 (並行)] {repo_full_name}") # ログが多すぎる可能性があるのでコメントアウト/調整
                try:
                    repo_commits = await self.get_commits_from_github_api(
                        repo_owner, repo_name, max_commits=max_commits_per_repo 
                    )
                    
                    if repo_commits:
                        for commit in repo_commits:
                            commit["repository"] = repo_full_name
                        # logger.info(f"[リポジトリ分析完了 (並行)] {repo_full_name}: {len(repo_commits)}件のコミット取得")
                        return repo_commits
                    else:
                        # logger.info(f"[リポジトリスキップ (並行)] {repo_full_name}: コミットが見つかりません")
                        return None
                except Exception as e:
                    logger.error(f"[リポジトリエラー (並行)] {repo_full_name}: {str(e)}")
                    return None

        tasks = [_fetch_and_process_repo_commits(repo) for repo in repositories]
        repo_commit_results = await asyncio.gather(*tasks)

        current_total_commits = 0
        for commits_from_one_repo in repo_commit_results:
            if commits_from_one_repo:
                if commits_from_one_repo[0]["repository"] not in analyzed_repos_names: # 1件でもコミットがあれば分析済みとする
                    analyzed_repos_names.append(commits_from_one_repo[0]["repository"])

                for commit in commits_from_one_repo:
                    if current_total_commits < max_total_commits:
                        all_commits_data.append(commit)
                        current_total_commits += 1
                    else:
                        break 
            if current_total_commits >= max_total_commits:
                logger.info(f"[ユーザーコミット分析] 最大コミット数({max_total_commits})に達したため、収集を部分的に停止")
                break 

        all_commits_data.sort(key=lambda x: x["date"], reverse=True)
        final_commits = all_commits_data # スライスは呼び出し側で行うか、ここでmax_total_commitsを厳守する

        logger.info(f"[ユーザーコミット分析完了] {username}: {len(analyzed_repos_names)}リポジトリから{len(final_commits)}件のコミットを収集")
        
        return final_commits, analyzed_repos_names, len(repositories)

    async def get_commits_from_github_api(
        self, owner: str, repo_name: str, max_commits: int = 1000, default_branch: str = "main"
    ) -> List[Dict]:
        """GitHub API (GraphQL) を使用してコミット情報を取得する"""
        
        commits_data: List[Dict] = []
        has_next_page = True
        end_cursor: Optional[str] = None
        commits_fetched = 0

        # mainブランチのコミット履歴を取得するクエリ
        # ref(qualifiedName: ...) でブランチを指定可能だが、まずはdefaultBranchRefを使う
        query_template = """
        query GetCommits($owner: String!, $repo: String!, $num: Int!, $cursor: String) {
          repository(owner: $owner, name: $repo) {
            defaultBranchRef {
              target {
                ... on Commit {
                  history(first: $num, after: $cursor) {
                    pageInfo {
                      hasNextPage
                      endCursor
                    }
                    nodes {
                      oid
                      author {
                        name
                        email
                        user {
                            login
                        }
                      }
                      message
                      committedDate
                    }
                  }
                }
              }
            }
          }
          rateLimit { limit remaining resetAt }
        }
        """
        
        while has_next_page and commits_fetched < max_commits:
            
            # 一度に取得するコミット数を調整（最大100件、残りの必要数）
            num_to_fetch = min(100, max_commits - commits_fetched)
            
            variables = {
                "owner": owner,
                "repo": repo_name,
                "num": num_to_fetch,
                "cursor": end_cursor,
                # "defaultBranch": default_branch # 必要に応じてブランチ指定
            }
            
            try:
                response_data = self._make_graphql_request(query_template, variables)
                if "errors" in response_data:
                    logger.error(f"GraphQLエラー: {response_data['errors']}")
                    raise Exception(f"GraphQLエラー: {response_data['errors']}")

                repo_info = response_data.get("data", {}).get("repository")
                if not repo_info or not repo_info.get("defaultBranchRef") or not repo_info["defaultBranchRef"].get("target") :
                    logger.warning(f"リポジトリ {owner}/{repo_name} またはデフォルトブランチのコミット履歴が見つかりません。")
                    break # リポジトリが見つからないか、ブランチにコミットがない
                
                history = repo_info["defaultBranchRef"]["target"].get("history")
                if not history:
                    logger.info(f"リポジトリ {owner}/{repo_name} のデフォルトブランチにコミット履歴がありません。")
                    break

                for node in history.get("nodes", []):
                    if commits_fetched >= max_commits:
                        break
                    
                    author_name = node.get("author", {}).get("name")
                    # GitHubユーザーがいる場合はそちらを優先
                    if node.get("author", {}).get("user") and node["author"]["user"].get("login"):
                         author_name = node["author"]["user"]["login"]
                    
                    commits_data.append({
                        "hash": node.get("oid"),
                        "author": author_name,
                        "email": node.get("author", {}).get("email"),
                        "message": node.get("message", "").strip(),
                        "date": datetime.fromisoformat(node.get("committedDate").replace("Z", "+00:00")),
                    })
                    commits_fetched += 1
                
                page_info = history.get("pageInfo", {})
                has_next_page = page_info.get("hasNextPage", False)
                end_cursor = page_info.get("endCursor")
                
                if not has_next_page:
                    logger.info(f"{owner}/{repo_name}: 全てのコミットを取得しました。({commits_fetched}件)")
                    break
                
                logger.info(f"{owner}/{repo_name}: {commits_fetched}件のコミットを取得。次のページ: {has_next_page}")

            except requests.exceptions.RequestException as e:
                logger.error(f"GitHub APIリクエストエラー: {e}")
                raise Exception(f"GitHub APIリクエストエラー: {e}")
            except Exception as e:
                logger.error(f"コミット取得中に予期せぬエラー: {e}")
                raise Exception(f"コミット取得中に予期せぬエラー: {e}")

        return commits_data[:max_commits] # 念のためスライス

    # clone_repository, get_commits, cleanup は削除 (またはコメントアウト)
    # def clone_repository(self, owner: str, repo: str) -> git.Repo:
    #     ...
    # def get_commits(self, repo: git.Repo, max_commits: int = 1000) -> List[Dict]:
    #     ...
    # def cleanup(self):
    #     ... 