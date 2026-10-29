# -*- coding: utf-8 -*-
"""
文件与片段索引（C 侧，10/26）：多份材料 → 片段编号 → 按问题检索原文

    save_file(filename, content_type, raw)  → 存储文件 + 切片段（chunk_id）
    list_files()                            → 文件列表（不含全文）
    get_file(file_id)                       → 文件详情 + 片段
    search_files(query, file_ids, top_k)    → 片段级检索（确定性打分，不调模型）
    collect_text(file_ids)                  → 拼接原文（给追问用）

存储：backend/data/files.json（已 gitignore）
"""
import json
import os
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from pdf_analyzer import extract_pdf_text

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
STORE_PATH = os.path.join(DATA_DIR, "files.json")
_LOCK = threading.Lock()
TZ = timezone(timedelta(hours=8))

FILE_MAX_BYTES = 10 * 1024 * 1024
ALLOWED_EXTS = (".txt", ".md", ".pdf")
CHUNK_SIZE = 400
CHUNK_OVERLAP = 80
_PUNCT = re.compile(r"[\s，。；：、！？,.!?:;\"'（）()\[\]【】《》<>…—\-]+")


def _load() -> Dict[str, dict]:
    if not os.path.exists(STORE_PATH):
        return {}
    try:
        with open(STORE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save(data: Dict[str, dict]) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STORE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STORE_PATH)


def _split_chunks(text: str) -> List[dict]:
    text = text.strip()
    if not text:
        return []
    step = CHUNK_SIZE - CHUNK_OVERLAP
    chunks, start, n = [], 0, len(text)
    while start < n:
        end = min(start + CHUNK_SIZE, n)
        if end < n:
            seg = text[start:end]
            cut = max(seg.rfind("。"), seg.rfind("；"), seg.rfind("\n"))
            if cut >= CHUNK_SIZE // 2:
                end = start + cut + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append({"chunk_id": "", "index": len(chunks), "text": chunk,
                           "char_start": start, "char_end": end})
        if end >= n:
            break
        start = max(end - CHUNK_OVERLAP, start + 1)
    return chunks


def _norm(text: str) -> str:
    return _PUNCT.sub("", str(text or ""))


def _bigrams(text: str) -> set:
    s = _norm(text)
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else ({s} if s else set())


def score(query: str, text: str) -> float:
    q, t = _norm(query), _norm(text)
    if not q or not t:
        return 0.0
    bg = _bigrams(q)
    hit = sum(1 for g in bg if g in t)
    s = hit / max(len(bg), 1)
    if q in t:
        s += 0.5
    return round(s, 4)


def _public(record: dict) -> dict:
    return {
        "file_id": record["file_id"], "filename": record["filename"],
        "content_type": record.get("content_type", ""), "size": record.get("size", 0),
        "chars": record.get("chars", 0), "chunk_count": len(record.get("chunks") or []),
        "created_at": record.get("created_at"),
    }


def save_file(filename: str, content_type: str, raw: bytes, session_id: str = "default") -> dict:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ALLOWED_EXTS:
        raise ValueError("仅支持 TXT / MD / PDF 文件（收到：%s）" % (ext or "未知"))
    if not raw:
        raise ValueError("文件内容为空")
    if len(raw) > FILE_MAX_BYTES:
        raise ValueError("文件不能超过 10 MB（当前 %.1f MB）" % (len(raw) / 1024 / 1024))

    if ext == ".pdf":
        text, _meta, err = extract_pdf_text(raw)
        if err:
            raise ValueError(err)
    else:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw.decode("gbk")
            except UnicodeDecodeError:
                raise ValueError("文本文件编码无法识别，请另存为 UTF-8")

    text = (text or "").strip()
    if not text:
        raise ValueError("文件中没有可提取的文字")

    file_id = "file_" + uuid.uuid4().hex[:8]
    chunks = _split_chunks(text)
    for i, c in enumerate(chunks):
        c["chunk_id"] = "%s_c%d" % (file_id, i + 1)
    record = {
        "file_id": file_id, "filename": filename, "content_type": content_type,
        "size": len(raw), "chars": len(text), "text": text, "chunks": chunks,
        "created_at": datetime.now(TZ).isoformat(),
        "session_id": session_id or "default",
    }
    with _LOCK:
        data = _load()
        data[file_id] = record
        _save(data)
    return _public(record)


def list_files(session_id: str = "default") -> List[dict]:
    owner = session_id or "default"
    with _LOCK:
        data = _load()
    records = [r for r in data.values() if (r.get("session_id") or "default") == owner]
    return [_public(r) for r in sorted(records, key=lambda x: x.get("created_at", ""), reverse=True)]


def get_file(file_id: str, session_id: str = "default") -> Optional[dict]:
    with _LOCK:
        data = _load()
    rec = data.get(file_id)
    if not rec or (rec.get("session_id") or "default") != (session_id or "default"):
        return None
    return {**_public(rec), "chunks": rec.get("chunks") or []}


def search_files(query: str, file_ids: Optional[List[str]] = None, top_k: int = 5,
                 session_id: str = "default") -> List[dict]:
    if not _norm(query):
        return []
    with _LOCK:
        data = _load()
    hits = []
    owner = session_id or "default"
    for rec in data.values():
        if (rec.get("session_id") or "default") != owner:
            continue
        if file_ids and rec["file_id"] not in file_ids:
            continue
        for c in rec.get("chunks") or []:
            s = score(query, c.get("text", ""))
            if s <= 0:
                continue
            hits.append({
                "file_id": rec["file_id"], "filename": rec["filename"],
                "chunk_id": c["chunk_id"], "text": c.get("text", ""), "score": s,
            })
    hits.sort(key=lambda x: x["score"], reverse=True)
    return hits[:max(1, min(int(top_k or 5), 20))]


def collect_text(file_ids: Optional[List[str]] = None, session_id: str = "default") -> str:
    with _LOCK:
        data = _load()
    parts = []
    owner = session_id or "default"
    for rec in data.values():
        if (rec.get("session_id") or "default") != owner:
            continue
        if file_ids and rec["file_id"] not in file_ids:
            continue
        parts.append("【%s】\n%s" % (rec["filename"], rec.get("text", "")))
    return "\n\n".join(parts)

def delete_file(file_id: str, session_id: str = "default") -> bool:
    """删除本会话的文件；其他会话不可见、不可删。"""
    if not file_id:
        return False
    with _LOCK:
        data = _load()
        rec = data.get(file_id)
        if not rec or (rec.get("session_id") or "default") != (session_id or "default"):
            return False
        del data[file_id]
        _save(data)
    return True
