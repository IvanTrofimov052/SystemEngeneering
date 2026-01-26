from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "social.db"
UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", APP_DIR.parent / "uploads")).resolve()
FRONTEND_DIR = Path(os.environ.get("FRONTEND_DIR", APP_DIR.parent / "frontend")).resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
SECRET = os.environ.get("APP_SECRET", "dev-secret-change-me")

app = FastAPI(title="Social Network MVP", version="1.0.0")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


def _now_ts() -> int:
    return int(time.time())


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    token: str


class PostOut(BaseModel):
    id: int
    author_id: int
    author_name: str
    author_avatar_url: Optional[str]
    text: str
    image_url: Optional[str]
    created_at: str
    updated_at: Optional[str]
    likes_count: int
    comments_count: int
    liked_by_me: bool = False


class CommentOut(BaseModel):
    id: int
    post_id: int
    author_id: int
    author_name: str
    author_avatar_url: Optional[str]
    text: str
    created_at: str


class PostDetailOut(BaseModel):
    post: PostOut
    comments: list[CommentOut]
    liked_by_me: bool = False


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    avatar_url: Optional[str]
    created_at: str


class CommentIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class DB:
    def __init__(self, path: Path):
        self.path = path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn


_db = DB(DB_PATH)


def init_db() -> None:
    with _db.connect() as conn:
        conn.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                avatar_url TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                author_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                image_url TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                FOREIGN KEY(author_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                author_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
                FOREIGN KEY(author_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(post_id, user_id),
                FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_type TEXT NOT NULL,
                owner_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                type TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            """
        )


@app.on_event("startup")
def _on_startup() -> None:
    init_db()


@app.get("/")
def index():
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Фронтенд не найден")
    return FileResponse(index_path)


@app.get("/login")
def login_page():
    page_path = FRONTEND_DIR / "login.html"
    if not page_path.exists():
        raise HTTPException(status_code=404, detail="Фронтенд не найден")
    return FileResponse(page_path)


@app.get("/register")
def register_page():
    page_path = FRONTEND_DIR / "register.html"
    if not page_path.exists():
        raise HTTPException(status_code=404, detail="Фронтенд не найден")
    return FileResponse(page_path)


@app.get("/posts/new")
def new_post_page():
    page_path = FRONTEND_DIR / "editor.html"
    if not page_path.exists():
        raise HTTPException(status_code=404, detail="Фронтенд не найден")
    return FileResponse(page_path)


@app.get("/posts/{post_id}/edit")
def edit_post_page(post_id: int):
    page_path = FRONTEND_DIR / "editor.html"
    if not page_path.exists():
        raise HTTPException(status_code=404, detail="Фронтенд не найден")
    return FileResponse(page_path)


@app.get("/post/{post_id}")
def view_post_page(post_id: int):
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Фронтенд не найден")
    return FileResponse(index_path)


# --- Auth helpers ---

def _hash_password(password: str, salt: str) -> str:
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    return _hash_password(password, salt) == stored


def _create_token(user_id: int) -> str:
    raw = f"{user_id}:{secrets.token_hex(16)}:{_now_ts()}:{SECRET}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _get_user_by_token(token: str) -> Optional[sqlite3.Row]:
    with _db.connect() as conn:
        row = conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?",
            (token,),
        ).fetchone()
    return row


def _require_user(request: Request) -> sqlite3.Row:
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")
    user = _get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный токен")
    return user


# --- File helpers ---

def _save_upload(file: UploadFile, prefix: str) -> str:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не выбран")
    ext = Path(file.filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        raise HTTPException(status_code=400, detail="Недопустимый формат изображения")
    name = f"{prefix}_{secrets.token_hex(8)}{ext}"
    dest = UPLOAD_DIR / name
    contents = file.file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Пустой файл")
    dest.write_bytes(contents)
    return f"/uploads/{name}"


# --- Endpoints ---

@app.post("/auth/register", response_model=TokenOut)
def register(payload: RegisterIn):
    salt = secrets.token_hex(8)
    password_hash = _hash_password(payload.password, salt)
    created_at = _now_iso()
    with _db.connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (payload.name, payload.email.lower(), password_hash, created_at),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Email уже используется")
        user_id = cur.lastrowid
        token = _create_token(user_id)
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user_id, created_at),
        )
    return TokenOut(token=token)


@app.post("/auth/login", response_model=TokenOut)
def login(payload: LoginIn):
    with _db.connect() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (payload.email.lower(),)).fetchone()
        if not user or not _verify_password(payload.password, user["password_hash"]):
            raise HTTPException(status_code=400, detail="Неверный email или пароль")
        token = _create_token(user["id"])
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user["id"], _now_iso()),
        )
    return TokenOut(token=token)


@app.get("/users/me", response_model=UserOut)
def me(user: sqlite3.Row = Depends(_require_user)):
    return UserOut(
        id=user["id"],
        name=user["name"],
        email=user["email"],
        avatar_url=user["avatar_url"],
        created_at=user["created_at"],
    )


@app.put("/users/me/avatar", response_model=UserOut)
def update_avatar(
    file: UploadFile = File(...),
    user: sqlite3.Row = Depends(_require_user),
):
    url = _save_upload(file, f"user{user['id']}_avatar")
    with _db.connect() as conn:
        conn.execute("UPDATE users SET avatar_url = ? WHERE id = ?", (url, user["id"]))
        conn.execute(
            "INSERT INTO media (owner_type, owner_id, url, type, created_at) VALUES (?, ?, ?, ?, ?)",
            ("user", user["id"], url, "image", _now_iso()),
        )
        updated = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    return UserOut(
        id=updated["id"],
        name=updated["name"],
        email=updated["email"],
        avatar_url=updated["avatar_url"],
        created_at=updated["created_at"],
    )


@app.post("/posts", response_model=PostOut)
def create_post(
    text: str = Form(...),
    image: Optional[UploadFile] = File(None),
    user: sqlite3.Row = Depends(_require_user),
):
    if not text.strip():
        raise HTTPException(status_code=400, detail="Текст поста обязателен")
    image_url = _save_upload(image, f"post{user['id']}") if image else None
    created_at = _now_iso()
    with _db.connect() as conn:
        cur = conn.execute(
            "INSERT INTO posts (author_id, text, image_url, created_at) VALUES (?, ?, ?, ?)",
            (user["id"], text.strip(), image_url, created_at),
        )
        post_id = cur.lastrowid
        if image_url:
            conn.execute(
                "INSERT INTO media (owner_type, owner_id, url, type, created_at) VALUES (?, ?, ?, ?, ?)",
                ("post", post_id, image_url, "image", created_at),
            )
    return _get_post_out(post_id)


@app.put("/posts/{post_id}", response_model=PostOut)
def update_post(
    post_id: int,
    text: str = Form(...),
    image: Optional[UploadFile] = File(None),
    remove_image: bool = Form(False),
    user: sqlite3.Row = Depends(_require_user),
):
    if not text.strip():
        raise HTTPException(status_code=400, detail="Текст поста обязателен")
    with _db.connect() as conn:
        post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not post:
            raise HTTPException(status_code=404, detail="Пост не найден")
        if post["author_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Нет доступа")
        image_url = post["image_url"]
        if image:
            image_url = _save_upload(image, f"post{user['id']}")
            conn.execute(
                "INSERT INTO media (owner_type, owner_id, url, type, created_at) VALUES (?, ?, ?, ?, ?)",
                ("post", post_id, image_url, "image", _now_iso()),
            )
        elif remove_image:
            image_url = None
        conn.execute(
            "UPDATE posts SET text = ?, image_url = ?, updated_at = ? WHERE id = ?",
            (text.strip(), image_url, _now_iso(), post_id),
        )
    return _get_post_out(post_id)


@app.delete("/posts/{post_id}")
def delete_post(post_id: int, user: sqlite3.Row = Depends(_require_user)):
    with _db.connect() as conn:
        post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not post:
            raise HTTPException(status_code=404, detail="Пост не найден")
        if post["author_id"] != user["id"]:
            raise HTTPException(status_code=403, detail="Нет доступа")
        conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    return {"status": "ok"}


@app.get("/feed", response_model=list[PostOut])
def feed(limit: int = 20, offset: int = 0, request: Request = None):
    limit = max(1, min(limit, 50))
    offset = max(0, offset)
    token = ""
    if request is not None:
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
    user = _get_user_by_token(token) if token else None
    with _db.connect() as conn:
        if user:
            rows = conn.execute(
                """
                SELECT p.*, u.name AS author_name, u.avatar_url AS author_avatar_url,
                       (SELECT COUNT(*) FROM likes l WHERE l.post_id = p.id) AS likes_count,
                       (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS comments_count,
                       EXISTS(
                           SELECT 1 FROM likes l
                           WHERE l.post_id = p.id AND l.user_id = ?
                       ) AS liked_by_me
                FROM posts p
                JOIN users u ON u.id = p.author_id
                ORDER BY p.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (user["id"], limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT p.*, u.name AS author_name, u.avatar_url AS author_avatar_url,
                       (SELECT COUNT(*) FROM likes l WHERE l.post_id = p.id) AS likes_count,
                       (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS comments_count,
                       0 AS liked_by_me
                FROM posts p
                JOIN users u ON u.id = p.author_id
                ORDER BY p.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
    return [
        PostOut(
            id=row["id"],
            author_id=row["author_id"],
            author_name=row["author_name"],
            author_avatar_url=row["author_avatar_url"],
            text=row["text"],
            image_url=row["image_url"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            likes_count=row["likes_count"],
            comments_count=row["comments_count"],
            liked_by_me=bool(row["liked_by_me"]),
        )
        for row in rows
    ]


@app.get("/posts/{post_id}", response_model=PostDetailOut)
def get_post(post_id: int, request: Request):
    post = _get_post_out(post_id)
    with _db.connect() as conn:
        comments = conn.execute(
            """
            SELECT c.*, u.name AS author_name, u.avatar_url AS author_avatar_url
            FROM comments c
            JOIN users u ON u.id = c.author_id
            WHERE c.post_id = ?
            ORDER BY c.created_at ASC
            """,
            (post_id,),
        ).fetchall()
    comment_list = [
        CommentOut(
            id=row["id"],
            post_id=row["post_id"],
            author_id=row["author_id"],
            author_name=row["author_name"],
            author_avatar_url=row["author_avatar_url"],
            text=row["text"],
            created_at=row["created_at"],
        )
        for row in comments
    ]
    liked_by_me = False
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if token:
        user = _get_user_by_token(token)
        if user:
            with _db.connect() as conn:
                like = conn.execute(
                    "SELECT 1 FROM likes WHERE post_id = ? AND user_id = ?",
                    (post_id, user["id"]),
                ).fetchone()
                liked_by_me = like is not None
    return PostDetailOut(post=post, comments=comment_list, liked_by_me=liked_by_me)


@app.post("/posts/{post_id}/comments", response_model=CommentOut)
def add_comment(post_id: int, payload: CommentIn, user: sqlite3.Row = Depends(_require_user)):
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Текст комментария обязателен")
    created_at = _now_iso()
    with _db.connect() as conn:
        post = conn.execute("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not post:
            raise HTTPException(status_code=404, detail="Пост не найден")
        cur = conn.execute(
            "INSERT INTO comments (post_id, author_id, text, created_at) VALUES (?, ?, ?, ?)",
            (post_id, user["id"], payload.text.strip(), created_at),
        )
        comment_id = cur.lastrowid
    return CommentOut(
        id=comment_id,
        post_id=post_id,
        author_id=user["id"],
        author_name=user["name"],
        author_avatar_url=user["avatar_url"],
        text=payload.text.strip(),
        created_at=created_at,
    )


@app.post("/posts/{post_id}/like")
def like_post(post_id: int, user: sqlite3.Row = Depends(_require_user)):
    with _db.connect() as conn:
        post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if not post:
            raise HTTPException(status_code=404, detail="Пост не найден")
        try:
            conn.execute(
                "INSERT INTO likes (post_id, user_id, created_at) VALUES (?, ?, ?)",
                (post_id, user["id"], _now_iso()),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=400, detail="Лайк уже поставлен")
    return {"status": "ok"}


@app.delete("/posts/{post_id}/like")
def unlike_post(post_id: int, user: sqlite3.Row = Depends(_require_user)):
    with _db.connect() as conn:
        conn.execute("DELETE FROM likes WHERE post_id = ? AND user_id = ?", (post_id, user["id"]))
    return {"status": "ok"}


@app.get("/media/{filename}")
def get_media(filename: str):
    path = UPLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(path)


# --- helpers ---

def _get_post_out(post_id: int) -> PostOut:
    with _db.connect() as conn:
        row = conn.execute(
            """
            SELECT p.*, u.name AS author_name, u.avatar_url AS author_avatar_url,
                   (SELECT COUNT(*) FROM likes l WHERE l.post_id = p.id) AS likes_count,
                   (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.id) AS comments_count
            FROM posts p
            JOIN users u ON u.id = p.author_id
            WHERE p.id = ?
            """,
            (post_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Пост не найден")
    return PostOut(
        id=row["id"],
        author_id=row["author_id"],
        author_name=row["author_name"],
        author_avatar_url=row["author_avatar_url"],
        text=row["text"],
        image_url=row["image_url"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        likes_count=row["likes_count"],
        comments_count=row["comments_count"],
        liked_by_me=False,
    )
