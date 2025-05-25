from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class RepositoryRequest(BaseModel):
    owner: str
    repo: str

class UserRequest(BaseModel):
    username: str

class CommitData(BaseModel):
    hash: str
    author: str
    email: str
    message: str
    date: datetime
    repository: Optional[str] = None  # ユーザー分析の場合にリポジトリ名を含める

class RepositoryResponse(BaseModel):
    owner: str
    repo: str
    commits: List[CommitData]
    total_commits: int

class UserAnalysisResponse(BaseModel):
    username: str
    repositories: List[str]
    commits: List[CommitData]
    total_commits: int
    total_repositories: int

class KwicResult(BaseModel):
    context: str
    keyword: str
    left: str
    right: str
    commit_hash: str
    next_token: Optional[str] = None # Raw next token, for logic
    next_pos: Optional[str] = None   # Raw next POS, for logic
    # For display purposes directly in the result item
    sort_metric_label: Optional[str] = None # e.g., "後続単語頻度", "後続品詞頻度"
    sort_metric_value: Optional[str] = None # e.g., "5回", "VERB (3回)"

class KwicResponse(BaseModel):
    keyword: str
    search_type: str
    window_size: int
    results: List[KwicResult]
    sort_type: Optional[str] = None # To confirm to the frontend how it was sorted

class NgramData(BaseModel):
    ngram: str
    frequency: int
    rank: int

class NgramResponse(BaseModel):
    ngrams: List[NgramData]
    total_ngrams: int

class AuthorData(BaseModel):
    author: str
    email: str
    commit_count: int
    avg_message_length: float
    common_words: List[str]
    total_chars: int

class AuthorResponse(BaseModel):
    authors: List[AuthorData]
    total_authors: int 