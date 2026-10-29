# src/notification_extractor.py
import json
import os
import io
import re
import uuid
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum

try:
    from jsonschema import validate, ValidationError
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

TZ = timezone(timedelta(hours=8))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("notification_extractor")

class Mode(str, Enum):
    SIMPLE = "simple"
    STANDARD = "standard"
    COMPLEX = "complex"

class Status(str, Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    FAILED = "failed"
    DELAYED = "delayed"
    PENDING_REVIEW = "pending_review"
    SUBMITTED = "submitted"
    NEED_RESUBMIT = "need_resubmit"

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

def _safe_list(v: Any) -> List:
    return v if isinstance(v, list) else []

def _safe_dict(v: Any) -> Optional[Dict]:
    return v if isinstance(v, dict) else None

def _safe_str(v: Any, default: str = "") -> str:
    return v if isinstance(v, str) else default

def normalize_enum(value: Any, enum_cls, default: str) -> str:
    try:
        return enum_cls(value).value
    except (ValueError, TypeError):
        return default

def parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s or not isinstance(s, str):
        return None
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt
    except ValueError:
        return None

def is_valid_iso(s: Optional[str]) -> bool:
    return parse_iso(s) is not None

@dataclass
class SourceRef:
    quote: str
    doc_id: Optional[str] = None
    doc_version: Optional[str] = None
    page: Optional[int] = None
    anchor_id: Optional[str] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    chunk_id: Optional[str] = None
    bbox: Optional[List[int]] = None

    def to_dict(self) -> Dict:
        result = {"quote": self.quote}
        for k in ["doc_id", "doc_version", "page", "anchor_id", "char_start", "char_end", "chunk_id", "bbox"]:
            v = getattr(self, k)
            if v is not None:
                result[k] = v
        return result

    @classmethod
    def from_dict(cls, d: Dict) -> "SourceRef":
        return cls(
            quote=_safe_str(d.get("quote")),
            doc_id=d.get("doc_id"),
            doc_version=d.get("doc_version"),
            page=d.get("page"),
            anchor_id=d.get("anchor_id"),
            char_start=d.get("char_start"),
            char_end=d.get("char_end"),
            chunk_id=d.get("chunk_id"),
            bbox=d.get("bbox"),
        )

@dataclass
class DocumentChunk:
    chunk_id: str
    content: str
    doc_name: str = "document"
    doc_id: str = "doc_1"
    page: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "chunk_id": self.chunk_id,
            "content": self.content,
            "doc_name": self.doc_name,
            "doc_id": self.doc_id,
        }
        if self.page is not None:
            result["page"] = self.page
        if self.char_start is not None:
            result["char_start"] = self.char_start
        if self.char_end is not None:
            result["char_end"] = self.char_end
        if self.score is not None:
            result["score"] = self.score
        if self.metadata:
            result["metadata"] = self.metadata
        return result

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DocumentChunk":
        return cls(
            chunk_id=_safe_str(d.get("chunk_id")),
            content=_safe_str(d.get("content")),
            doc_name=_safe_str(d.get("doc_name"), "document"),
            doc_id=_safe_str(d.get("doc_id"), "doc_1"),
            page=d.get("page"),
            char_start=d.get("char_start"),
            char_end=d.get("char_end"),
            score=d.get("score"),
            metadata=d.get("metadata") or {},
        )

@dataclass
class Reminder:
    reminder_id: str
    offset_minutes: int = 120
    channels: List[str] = field(default_factory=lambda: ["app"])
    enabled: bool = True

    def to_dict(self) -> Dict:
        return {
            "reminder_id": self.reminder_id,
            "offset_minutes": self.offset_minutes,
            "channels": self.channels,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Reminder":
        return cls(
            reminder_id=_safe_str(d.get("reminder_id")) or f"rem_{uuid.uuid4().hex[:6]}",
            offset_minutes=d.get("offset_minutes", 120),
            channels=_safe_list(d.get("channels")) or ["app"],
            enabled=bool(d.get("enabled", True)),
        )

@dataclass
class Deadline:
    scope: str = "overall"
    label: str = "截止时间"
    start_at: Optional[str] = None
    due_at: Optional[str] = None
    end_at: Optional[str] = None
    all_day: bool = False
    source_ref: Optional[SourceRef] = None

    def to_dict(self) -> Dict:
        result = {"scope": self.scope, "label": self.label, "all_day": self.all_day}
        if self.start_at: result["start_at"] = self.start_at
        if self.due_at: result["due_at"] = self.due_at
        if self.end_at: result["end_at"] = self.end_at
        if self.source_ref: result["source_ref"] = self.source_ref.to_dict()
        return result

    @classmethod
    def from_dict(cls, d: Dict) -> "Deadline":
        src = _safe_dict(d.get("source_ref"))
        return cls(
            scope=_safe_str(d.get("scope"), "overall"),
            label=_safe_str(d.get("label"), "截止时间"),
            start_at=d.get("start_at") if is_valid_iso(d.get("start_at")) else None,
            due_at=d.get("due_at") if is_valid_iso(d.get("due_at")) else None,
            end_at=d.get("end_at") if is_valid_iso(d.get("end_at")) else None,
            all_day=bool(d.get("all_day", False)),
            source_ref=SourceRef.from_dict(src) if src else None,
        )

@dataclass
class Location:
    type: str = "offline"
    name: Optional[str] = None
    room: Optional[str] = None
    source_ref: Optional[SourceRef] = None

    def to_dict(self) -> Dict:
        result = {"type": self.type}
        if self.name: result["name"] = self.name
        if self.room: result["room"] = self.room
        if self.source_ref: result["source_ref"] = self.source_ref.to_dict()
        return result

    @classmethod
    def from_dict(cls, d: Dict) -> "Location":
        src = _safe_dict(d.get("source_ref"))
        return cls(
            type=_safe_str(d.get("type"), "offline"),
            name=d.get("name"),
            room=d.get("room"),
            source_ref=SourceRef.from_dict(src) if src else None,
        )

@dataclass
class Attachment:
    attachment_id: str
    attachment_name: str
    attachment_type: str = "file"
    source_ref: Optional[SourceRef] = None

    def to_dict(self) -> Dict:
        result = {"attachment_id": self.attachment_id, "attachment_name": self.attachment_name, "attachment_type": self.attachment_type}
        if self.source_ref: result["source_ref"] = self.source_ref.to_dict()
        return result

    @classmethod
    def from_dict(cls, d: Dict) -> "Attachment":
        src = _safe_dict(d.get("source_ref"))
        att_name = _safe_str(d.get("attachment_name")).strip()
        if not att_name and src:
            att_name = _safe_str(src.get("quote"))[:8] + "..."
        
        return cls(
            attachment_id=_safe_str(d.get("attachment_id")) or f"att_{uuid.uuid4().hex[:6]}",
            attachment_name=att_name if att_name else "未命名附件",
            attachment_type=_safe_str(d.get("attachment_type"), "file"),
            source_ref=SourceRef.from_dict(src) if src else None,
        )

@dataclass
class Material:
    material_id: str
    material_name: str
    material_type: str = "required"
    status: str = "pending"
    template_attachment_id: Optional[str] = None
    source_ref: Optional[SourceRef] = None
    is_suggestion: bool = False

    def to_dict(self) -> Dict:
        result = {"material_id": self.material_id, "material_name": self.material_name, "material_type": self.material_type, "status": self.status}
        if self.template_attachment_id: result["template_attachment_id"] = self.template_attachment_id
        if self.source_ref: result["source_ref"] = self.source_ref.to_dict()
        if self.is_suggestion: result["is_suggestion"] = True
        return result

    @classmethod
    def from_dict(cls, d: Dict) -> "Material":
        src = _safe_dict(d.get("source_ref"))
        m_name = _safe_str(d.get("material_name")).strip()
        if not m_name and src:
            m_name = _safe_str(src.get("quote"))[:8] + "..."
            
        return cls(
            material_id=_safe_str(d.get("material_id")) or f"mat_{uuid.uuid4().hex[:6]}",
            material_name=m_name if m_name else "未命名材料",
            material_type=_safe_str(d.get("material_type"), "required"),
            status=_safe_str(d.get("status"), "pending"),
            template_attachment_id=d.get("template_attachment_id"),
            source_ref=SourceRef.from_dict(src) if src else None,
            is_suggestion=bool(d.get("is_suggestion", False))
        )

@dataclass
class Review:
    required: bool = False
    reviewer: Optional[Dict] = None
    status: Optional[str] = None

    def to_dict(self) -> Dict:
        result = {"required": self.required}
        if self.reviewer: result["reviewer"] = self.reviewer
        if self.status: result["status"] = self.status
        return result

    @classmethod
    def from_dict(cls, d: Dict) -> "Review":
        return cls(
            required=bool(d.get("required", False)),
            reviewer=_safe_dict(d.get("reviewer")),
            status=d.get("status"),
        )

@dataclass
class Todo:
    todo_id: str
    action: str
    status: str = "pending"
    source_ref: Optional[SourceRef] = None
    is_suggestion: bool = False

    def to_dict(self) -> Dict:
        result = {"todo_id": self.todo_id, "action": self.action, "status": self.status}
        if self.source_ref: result["source_ref"] = self.source_ref.to_dict()
        if self.is_suggestion: result["is_suggestion"] = True
        return result

    @classmethod
    def from_dict(cls, d: Any) -> "Todo":
        if isinstance(d, str):
            return cls(
                todo_id=f"todo_{uuid.uuid4().hex[:6]}",
                action=d,
                status="pending",
                source_ref=None,
                is_suggestion=False
            )

        src = _safe_dict(d.get("source_ref"))
        return cls(
            todo_id=_safe_str(d.get("todo_id")) or f"todo_{uuid.uuid4().hex[:6]}",
            action=_safe_str(d.get("action")),
            status=_safe_str(d.get("status"), "pending"),
            source_ref=SourceRef.from_dict(src) if src else None,
            is_suggestion=bool(d.get("is_suggestion", False))
        )

@dataclass
class Step:
    step_id: str
    order: int
    title: str
    status: str = "not_started"
    parent_id: Optional[str] = None
    is_sub_step: bool = False
    due_at: Optional[str] = None
    materials: List[str] = field(default_factory=list)
    attachments: List[str] = field(default_factory=list)
    dependencies: List[Dict] = field(default_factory=list)
    owner: Optional[Dict] = None
    review: Optional[Review] = None
    sub_step_list: List["Step"] = field(default_factory=list)
    source_ref: Optional[SourceRef] = None
    is_suggestion: bool = False

    def to_dict(self) -> Dict:
        id_key = "sub_step_id" if self.is_sub_step else "step_id"
        result = {id_key: self.step_id, "order": self.order, "title": self.title, "status": self.status}
        if self.parent_id: result["parent_id"] = self.parent_id
        if self.due_at: result["due_at"] = self.due_at
        if self.materials: result["materials"] = self.materials
        if self.attachments: result["attachments"] = self.attachments
        if self.dependencies: result["dependencies"] = self.dependencies
        if self.owner: result["owner"] = self.owner
        if self.review: result["review"] = self.review.to_dict()
        if self.sub_step_list: result["sub_step_list"] = [s.to_dict() for s in self.sub_step_list]
        if self.source_ref: result["source_ref"] = self.source_ref.to_dict()
        if self.is_suggestion: result["is_suggestion"] = True
        return result

    @classmethod
    def from_dict(cls, d: Any, is_sub_step: bool = False) -> "Step":
        if isinstance(d, str):
            return cls(
                step_id=f"step_{uuid.uuid4().hex[:6]}",
                order=1,
                title=d,
                status="not_started",
                is_suggestion=False
            )

        src = _safe_dict(d.get("source_ref"))
        rev = _safe_dict(d.get("review"))
        sid = d.get("sub_step_id") if is_sub_step else d.get("step_id")
        if not sid: sid = d.get("step_id") or d.get("sub_step_id") or f"step_{uuid.uuid4().hex[:6]}"
        
        raw_deps = _safe_list(d.get("dependencies"))
        parsed_deps = []
        for dep in raw_deps:
            if isinstance(dep, str):
                parsed_deps.append({"type": "finish_to_start", "step_id": dep})
            elif isinstance(dep, dict):
                parsed_deps.append(dep)

        return cls(
            step_id=_safe_str(sid),
            order=int(d.get("order", 1)),
            title=_safe_str(d.get("title")),
            status=normalize_enum(d.get("status"), Status, "not_started"),
            parent_id=d.get("parent_id"),
            is_sub_step=is_sub_step,
            due_at=d.get("due_at") if is_valid_iso(d.get("due_at")) else None,
            materials=_safe_list(d.get("materials")),
            attachments=_safe_list(d.get("attachments")),
            dependencies=parsed_deps,
            owner=_safe_dict(d.get("owner")),
            review=Review.from_dict(rev) if rev else None,
            sub_step_list=[Step.from_dict(s, is_sub_step=True) for s in _safe_list(d.get("sub_step_list"))],
            source_ref=SourceRef.from_dict(src) if src else None,
            is_suggestion=bool(d.get("is_suggestion", False))
        )

@dataclass
class Warning:
    warning_id: str
    warning_type: str
    mode_scope: str = "complex"
    severity: str = "medium"
    message: Optional[str] = None

    def to_dict(self) -> Dict:
        result = {"warning_id": self.warning_id, "warning_type": self.warning_type, "mode_scope": self.mode_scope, "severity": self.severity}
        if self.message: result["message"] = self.message
        return result

    @classmethod
    def from_dict(cls, d: Dict) -> "Warning":
        w_type = _safe_str(d.get("warning_type"))
        if not w_type:
            w_type = "deadline_risk"
            
        return cls(
            warning_id=_safe_str(d.get("warning_id")) or f"warn_{uuid.uuid4().hex[:6]}",
            warning_type=w_type,
            mode_scope=_safe_str(d.get("mode_scope"), "complex"),
            severity=_safe_str(d.get("severity"), "medium"),
            message=d.get("message"),
        )

@dataclass
class Matter:
    schema_version: str = "1.0"
    id: str = "matter_auto"
    mode: str = "simple"
    mode_source: str = "auto"
    complexity_score: float = 0.0
    detected_features: List[str] = field(default_factory=list)
    enabled_sections: List[str] = field(default_factory=list)
    title: str = ""
    priority: str = "medium"
    status: str = "not_started"
    status_source: str = "auto"
    timezone: str = "Asia/Shanghai"
    created_at: str = ""
    updated_at: str = ""
    deadline: Optional[Deadline] = None
    reminders: List[Reminder] = field(default_factory=list)
    default_location: Optional[Location] = None
    attachments: List[Attachment] = field(default_factory=list)
    materials: List[Material] = field(default_factory=list)
    step_list: List[Step] = field(default_factory=list)
    todo_list: List[Todo] = field(default_factory=list)
    warning_list: List[Warning] = field(default_factory=list)
    sources: List[SourceRef] = field(default_factory=list)

    def to_dict(self) -> Dict:
        result = {
            "schema_version": self.schema_version, "id": self.id, "mode": self.mode, "mode_source": self.mode_source,
            "complexity_score": self.complexity_score, "title": self.title, "priority": self.priority,
            "status": self.status, "status_source": self.status_source, "timezone": self.timezone,
            "created_at": self.created_at, "updated_at": self.updated_at
        }
        if self.detected_features: result["detected_features"] = self.detected_features
        if self.enabled_sections: result["enabled_sections"] = self.enabled_sections
        if self.deadline: result["deadline"] = self.deadline.to_dict()
        if self.reminders: result["reminders"] = [r.to_dict() for r in self.reminders]
        if self.default_location: result["default_location"] = self.default_location.to_dict()
        if self.attachments: result["attachments"] = [a.to_dict() for a in self.attachments]
        if self.materials: result["materials"] = [m.to_dict() for m in self.materials]
        if self.step_list: result["step_list"] = [s.to_dict() for s in self.step_list]
        if self.todo_list: result["todo_list"] = [t.to_dict() for t in self.todo_list]
        if self.warning_list: result["warning_list"] = [w.to_dict() for w in self.warning_list]
        if self.sources: result["sources"] = [s.to_dict() for s in self.sources]
        return result

    @classmethod
    def from_dict(cls, d: Dict) -> "Matter":
        m = cls()
        m.schema_version = _safe_str(d.get("schema_version"), "1.0")
        m.id = _safe_str(d.get("id"), "matter_auto")
        m.mode = normalize_enum(d.get("mode"), Mode, "simple")
        m.mode_source = _safe_str(d.get("mode_source"), "auto")
        m.complexity_score = float(d.get("complexity_score", 0.0))
        m.detected_features = _safe_list(d.get("detected_features"))
        m.enabled_sections = _safe_list(d.get("enabled_sections"))
        m.title = _safe_str(d.get("title"))
        m.priority = normalize_enum(d.get("priority"), Priority, "medium")
        m.status = normalize_enum(d.get("status"), Status, "not_started")
        m.status_source = _safe_str(d.get("status_source"), "auto")
        m.timezone = _safe_str(d.get("timezone"), "Asia/Shanghai")
        m.created_at = _safe_str(d.get("created_at"))
        m.updated_at = _safe_str(d.get("updated_at"))
        if _safe_dict(d.get("deadline")): m.deadline = Deadline.from_dict(d["deadline"])
        m.reminders = [Reminder.from_dict(r) for r in _safe_list(d.get("reminders"))]
        if _safe_dict(d.get("default_location")): m.default_location = Location.from_dict(d["default_location"])
        m.attachments = [Attachment.from_dict(a) for a in _safe_list(d.get("attachments"))]
        m.materials = [Material.from_dict(x) for x in _safe_list(d.get("materials"))]
        m.step_list = [Step.from_dict(s, is_sub_step=False) for s in _safe_list(d.get("step_list"))]
        m.todo_list = [Todo.from_dict(t) for t in _safe_list(d.get("todo_list"))]
        m.warning_list = [Warning.from_dict(w) for w in _safe_list(d.get("warning_list"))]
        m.sources = [SourceRef.from_dict(s) for s in _safe_list(d.get("sources"))]
        return m

MODE_FORBIDDEN_FIELDS = {
    "simple": {"owner", "assignees", "participants", "contact", "default_location", "key_points", "attachments", "materials", "step_list", "todo_list", "warning_list", "permissions", "audit_log", "comments", "recurrence"},
    "standard": {"recurrence", "permissions", "audit_log", "comments"},
    "complex": set(),
}
MODE_ALLOWED_SECTIONS = {
    "simple": ["summary", "schedule", "source"],
    "standard": ["summary", "schedule", "content", "steps", "materials", "source"],
    "complex": ["summary", "schedule", "content", "steps", "materials", "warnings", "governance", "source"],
}
STEP_FORBIDDEN_IN_NON_COMPLEX = {"sub_step_list", "dependencies", "parallel", "condition", "review", "owner", "assignees", "start_at", "reminders"}
STANDARD_WARNING_TYPES = {"deadline_risk", "missing_material"}

def enforce_mode(raw: Dict) -> Dict:
    if not isinstance(raw, dict): return raw
    mode = raw.get("mode", "simple")
    if mode not in MODE_FORBIDDEN_FIELDS: mode = "simple"; raw["mode"] = mode
    for f in MODE_FORBIDDEN_FIELDS[mode]: raw.pop(f, None)
    if mode in ("simple", "standard"):
        for step in _safe_list(raw.get("step_list")):
            if not isinstance(step, dict): continue
            for f in STEP_FORBIDDEN_IN_NON_COMPLEX: step.pop(f, None)
            for sub in _safe_list(step.get("sub_step_list")):
                if isinstance(sub, dict):
                    for f in STEP_FORBIDDEN_IN_NON_COMPLEX: sub.pop(f, None)
    if mode == "standard":
        raw["warning_list"] = [w for w in _safe_list(raw.get("warning_list")) if isinstance(w, dict) and w.get("warning_type") in STANDARD_WARNING_TYPES]
        if not raw["warning_list"]: raw.pop("warning_list", None)
    return raw

def enforce_enabled_sections(raw: Dict) -> Dict:
    if not isinstance(raw, dict): return raw
    raw["enabled_sections"] = MODE_ALLOWED_SECTIONS.get(raw.get("mode", "simple"), MODE_ALLOWED_SECTIONS["simple"])
    return raw


def normalize_step_orders(data: Dict) -> Dict:
    """把 step_list[].order 统一重排为 1..N，子步骤同理。

    真实模型偶尔会返回 [1,1] / [1,1,1,1]，前端按 order 排序时会出现
    顺序不稳定；这里不改变 step_id，只重排展示顺序。
    """
    if not isinstance(data, dict):
        return data
    for index, step in enumerate(data.get("step_list") or [], 1):
        if not isinstance(step, dict):
            continue
        step["order"] = index
        for sub_index, sub_step in enumerate(step.get("sub_step_list") or [], 1):
            if isinstance(sub_step, dict):
                sub_step["order"] = sub_index
    return data

FEATURE_WEIGHTS = {"has_deadline": 0.2, "has_multiple_reminders": 0.1, "has_multiple_steps": 0.2, "has_sub_steps": 0.1, "has_materials": 0.2, "has_review": 0.1, "has_dependencies": 0.1, "has_recurrence": 0.1}

def recompute_complexity(features: List[str]) -> float:
    # 保留 3 位小数，避免 0.2+0.2+0.2 = 0.6000000000000001 被误判为 complex
    return round(min(1.0, sum(FEATURE_WEIGHTS.get(f, 0.0) for f in features)), 3)

def decide_mode(features: List[str], score: float) -> str:
    if any(f in features for f in ("has_sub_steps", "has_review", "has_dependencies")): return "complex"
    if score < 0.3: return "simple"
    if score <= 0.6: return "standard"
    return "complex"

# 模型有时会把“指导老师签字”误判成审核、把并列步骤误判成依赖；
# 这里用原文关键词做一次特征校验，避免整条通知被错误升级为 complex。
REVIEW_KEYWORDS = ("审核", "评审", "初审", "复审", "审批", "复核", "盖章", "答辩", "公示")
DEPENDENCY_KEYWORDS = ("通过后", "审核通过后", "完成后", "之后", "才能", "须先", "合格后", "立项后", "批准后", "公示后")

def sanitize_features(features: List[str], text: str) -> List[str]:
    """只保留原文有依据的复杂特征；没有关键词就降级为普通特征。"""
    text = str(text or "")
    result = list(features or [])
    if "has_review" in result and not any(k in text for k in REVIEW_KEYWORDS):
        result.remove("has_review")
    if "has_dependencies" in result and not any(k in text for k in DEPENDENCY_KEYWORDS):
        result.remove("has_dependencies")
    return result

MATTER_SCHEMA = {
    "type": "object", "required": ["schema_version", "id", "mode", "title", "status"],
    "properties": {
        "schema_version": {"type": "string"}, "id": {"type": "string"}, "mode": {"enum": ["simple", "standard", "complex"]},
        "mode_source": {"enum": ["auto", "user"]}, "complexity_score": {"type": "number", "minimum": 0, "maximum": 1},
        "detected_features": {"type": "array", "items": {"type": "string"}}, "enabled_sections": {"type": "array", "items": {"type": "string"}},
        "title": {"type": "string"}, "priority": {"enum": ["low", "medium", "high", "urgent"]},
        "status": {"enum": ["not_started", "in_progress", "completed", "cancelled", "skipped", "failed", "delayed", "pending_review", "submitted", "need_resubmit"]},
        "timezone": {"type": "string"}, "deadline": {"type": ["object", "null"]}, "step_list": {"type": "array"},
        "materials": {"type": "array"}, "attachments": {"type": "array"}, "warning_list": {"type": "array"}, "sources": {"type": "array"},
        "todo_list": {"type": "array"}
    },
}

def validate_matter(data: Dict) -> Tuple[bool, Optional[str]]:
    if not HAS_JSONSCHEMA: return True, None
    try:
        validate(instance=data, schema=MATTER_SCHEMA)
        return True, None
    except ValidationError as e:
        return False, str(e)

class LLMClient:
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: Optional[str] = None, timeout: int = 60):
        cfg = self._load_local_config()
        self.api_key = api_key or cfg.get("LLM_API_KEY") or os.getenv("LLM_API_KEY", "")
        self.base_url = base_url or cfg.get("LLM_BASE_URL") or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.model = model or cfg.get("LLM_MODEL") or os.getenv("LLM_MODEL", "gpt-4o")
        self.timeout = cfg.get("LLM_TIMEOUT") or timeout

    @staticmethod
    def _load_local_config() -> Dict:
        try:
            from config_local import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT
            return {"LLM_API_KEY": LLM_API_KEY, "LLM_BASE_URL": LLM_BASE_URL, "LLM_MODEL": LLM_MODEL, "LLM_TIMEOUT": LLM_TIMEOUT}
        except ImportError:
            return {}

    def extract(self, notification_text: str, system_prompt: str) -> Dict:
        request_id = uuid.uuid4().hex[:8]
        logger.info("[%s] 开始解析：model=%s，文本长度=%d", request_id, self.model, len(notification_text))
        now_str = datetime.now(TZ).isoformat()
        system_content = system_prompt.replace("{{NOW}}", now_str).replace("{{USER_NOTIFICATION_TEXT}}", "")

        if not self.api_key:
            raise RuntimeError("LLM_API_KEY 未配置，无法解析通知")

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout)
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system_content}, {"role": "user", "content": notification_text}],
                temperature=0,
                response_format={"type": "json_object"},
                stream=True,
            )
            
            raw_text = ""
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    raw_text += chunk.choices[0].delta.content
            
            raw_text = raw_text.strip()
            if raw_text.startswith("```json"): raw_text = raw_text[7:]
            elif raw_text.startswith("```"): raw_text = raw_text[3:]
            if raw_text.endswith("```"): raw_text = raw_text[:-3]
            raw_text = raw_text.strip()
            
            if not raw_text:
                raise ValueError("大模型返回了空内容，可能是供应商接口超时或拒绝服务")
                
            try:
                raw = json.loads(raw_text)
            except json.JSONDecodeError as e:
                logger.error(f"JSON解析失败！原始返回内容：\n{raw_text}")
                raise ValueError(f"大模型输出格式错误，无法转为JSON: {e}")

            logger.info("[%s] API 完成：mode=%s", request_id, raw.get("mode"))
            return raw
        except Exception as e:
            logger.exception("[%s] LLM 调用失败：%s", request_id, e)
            raise

@dataclass
class ScheduledReminder:
    matter_id: str
    title: str
    fire_at: datetime
    channels: List[str]
    payload: Dict

class ReminderScheduler:
    def __init__(self): self.jobs: List[ScheduledReminder] = []
    def schedule_from_matter(self, matter: Matter) -> List[ScheduledReminder]:
        jobs = []
        if not matter.deadline or not matter.deadline.due_at: return jobs
        due = parse_iso(matter.deadline.due_at)
        if not due: return jobs
        for r in matter.reminders:
            if not r.enabled: continue
            fire_at = due - timedelta(minutes=r.offset_minutes)
            if fire_at <= datetime.now(TZ): continue
            jobs.append(ScheduledReminder(matter.id, matter.title, fire_at, r.channels, {"reminder_id": r.reminder_id}))
        self.jobs.extend(jobs)
        return jobs

class MatterExtractor:
    def __init__(self, llm: LLMClient, system_prompt: str):
        self.llm = llm
        self.system_prompt = system_prompt
        self.scheduler = ReminderScheduler()

    def process(self, source: str) -> Tuple[Optional[Matter], Optional[str]]:
        raw = self.llm.extract(source, self.system_prompt)
        
        if isinstance(raw.get("deadline"), str):
            raw["deadline"] = {"scope": "overall", "label": "截止时间", "due_at": raw["deadline"]}

        if isinstance(raw.get("title"), dict):
            raw["title"] = raw["title"].get("text") or raw["title"].get("title") or "未命名事项"
        elif not isinstance(raw.get("title"), str):
            raw["title"] = str(raw.get("title") or "未命名事项")

        features = _safe_list(raw.get("detected_features"))
        
        # ====== 增添：强行兜底，防止大模型漏识别特征导致降级 ======
        if not features:
            if raw.get("deadline"): features.append("has_deadline")
            if raw.get("materials"): features.append("has_materials")
            if _safe_list(raw.get("step_list")): features.append("has_multiple_steps")
            warnings = [w for w in _safe_list(raw.get("warning_list")) if isinstance(w, dict)]
            if any(w.get("warning_type") in ("review", "approval", "dependency") for w in warnings):
                features.append("has_review")
            raw["detected_features"] = features
        # ========================================================

        # 用原文校验模型识别出的复杂特征，避免“指导老师签字”被误判成审核
        features = sanitize_features(features, source)
        raw["detected_features"] = features

        score = round(recompute_complexity(features), 3)
        raw["complexity_score"] = score
        
        # ====== 结合大模型给的 mode 和公式算出的 mode，防止被降级 ======
        # 但如果模型给 complex，而原文里没有任何复杂特征/分数也不够，就不能盲信；
        # 否则“指导老师签字”这种普通通知会被升级成 complex，材料/步骤被错误保留。
        computed_mode = decide_mode(features, score)
        llm_mode = raw.get("mode", "simple")
        mode_priority = {"simple": 0, "standard": 1, "complex": 2}
        complex_supported = any(f in features for f in ("has_sub_steps", "has_review", "has_dependencies"))
        if llm_mode == "complex" and not complex_supported and score <= 0.6:
            raw["mode"] = computed_mode
        elif mode_priority.get(llm_mode, 0) > mode_priority.get(computed_mode, 0):
            raw["mode"] = llm_mode
        else:
            raw["mode"] = computed_mode
        # ==============================================================

        raw = enforce_mode(raw)
        raw = enforce_enabled_sections(raw)
        raw = normalize_step_orders(raw)

        ok, err = validate_matter(raw)
        if not ok: 
            logger.error(f"校验失败原始数据: {json.dumps(raw, ensure_ascii=False)}")
            return None, f"Schema 校验失败：{err}"

        matter = Matter.from_dict(raw)
        now_iso = datetime.now(TZ).isoformat()
        matter.created_at = matter.created_at or now_iso
        matter.updated_at = now_iso
        if matter.id == "matter_auto": matter.id = f"matter_{uuid.uuid4().hex[:8]}"
        if not matter.title: matter.title = "未命名事项"

        matter.scheduler_jobs = self.scheduler.schedule_from_matter(matter)
        return matter, None


# ==================== 10.25：文字型 PDF 内容提取 ====================

def extract_pdf_pages_and_text(pdf_input: Any, filename: str = "document.pdf") -> Dict[str, Any]:
    """
    10.25 任务：文字型 PDF 内容提取
    接收 PDF 路径 (str/Path)、bytes 或文件流，提取出纯文本与逐页结构。
    """
    if pdf_input is None:
        return {
            "success": False, "text": "", "pages": [], "total_pages": 0,
            "doc_name": filename, "is_scanned": False, "error": "PDF 输入内容为空"
        }

    try:
        try:
            import pymupdf as fitz
        except ImportError:
            try:
                import fitz
            except ImportError:
                fitz = None

        if fitz is not None:
            if isinstance(pdf_input, (str, Path)):
                path_obj = Path(pdf_input)
                if not path_obj.exists():
                    return {
                        "success": False, "text": "", "pages": [], "total_pages": 0,
                        "doc_name": filename, "is_scanned": False, "error": f"PDF 文件不存在: {pdf_input}"
                    }
                doc = fitz.open(str(path_obj))
                filename = path_obj.name
            elif isinstance(pdf_input, bytes):
                doc = fitz.open(stream=pdf_input, filetype="pdf")
            elif hasattr(pdf_input, "read"):
                data = pdf_input.read()
                doc = fitz.open(stream=data, filetype="pdf")
            else:
                return {
                    "success": False, "text": "", "pages": [], "total_pages": 0,
                    "doc_name": filename, "is_scanned": False, "error": "不支持的 PDF 输入类型"
                }

            pages = []
            page_text_blocks = []
            total_chars = 0
            for idx, page in enumerate(doc):
                text = (page.get_text() or "").strip()
                char_count = len(text)
                total_chars += char_count
                pages.append({
                    "page": idx + 1,
                    "text": text,
                    "char_count": char_count
                })
                if text:
                    page_text_blocks.append(f"【第 {idx + 1} 页】\n{text}")

            total_pages = len(doc)
            doc.close()
            full_text = "\n\n".join(page_text_blocks)
            is_scanned = bool(total_pages > 0 and total_chars < 15)

            return {
                "success": True,
                "text": full_text,
                "pages": pages,
                "total_pages": total_pages,
                "total_chars": total_chars,
                "doc_name": filename,
                "is_scanned": is_scanned,
                "error": None
            }
        else:
            try:
                import pypdf
                if isinstance(pdf_input, (str, Path)):
                    reader = pypdf.PdfReader(str(pdf_input))
                    filename = Path(pdf_input).name
                elif isinstance(pdf_input, bytes):
                    reader = pypdf.PdfReader(io.BytesIO(pdf_input))
                else:
                    reader = pypdf.PdfReader(pdf_input)

                pages = []
                page_text_blocks = []
                total_chars = 0
                for idx, page in enumerate(reader.pages):
                    text = (page.extract_text() or "").strip()
                    char_count = len(text)
                    total_chars += char_count
                    pages.append({"page": idx + 1, "text": text, "char_count": char_count})
                    if text:
                        page_text_blocks.append(f"【第 {idx + 1} 页】\n{text}")

                total_pages = len(reader.pages)
                full_text = "\n\n".join(page_text_blocks)
                is_scanned = bool(total_pages > 0 and total_chars < 15)
                return {
                    "success": True,
                    "text": full_text,
                    "pages": pages,
                    "total_pages": total_pages,
                    "total_chars": total_chars,
                    "doc_name": filename,
                    "is_scanned": is_scanned,
                    "error": None
                }
            except ImportError:
                return {
                    "success": False, "text": "", "pages": [], "total_pages": 0,
                    "doc_name": filename, "is_scanned": False,
                    "error": "未安装 PDF 解析库（pymupdf 或 pypdf），请先安装依赖"
                }
    except Exception as e:
        logger.exception("PDF 文本提取异常: %s", e)
        return {
            "success": False,
            "text": "",
            "pages": [],
            "total_pages": 0,
            "doc_name": filename,
            "is_scanned": False,
            "error": f"PDF 文本提取失败: {str(e)}"
        }


# ==================== 10.26：片段划分与编号 (Chunking) ====================

def chunk_document_text(
    text: str,
    doc_name: str = "通知原文",
    doc_id: str = "doc_1",
    page: Optional[int] = None,
    chunk_size: int = 250,
    overlap: int = 40,
) -> List[DocumentChunk]:
    """
    10.26 任务：将通知内容切分成便于查找的片段并规范编号
    """
    text = (text or "").strip()
    if not text:
        return []

    split_pattern = r"(?<=[。\n！!？?；;])"
    sentences = [s.strip() for s in re.split(split_pattern, text) if s.strip()]
    if not sentences:
        sentences = [text]

    chunks: List[DocumentChunk] = []
    cur_sentences = []
    cur_len = 0
    chunk_index = 1
    char_offset = 0

    for s in sentences:
        s_len = len(s)
        if cur_len + s_len > chunk_size and cur_sentences:
            content = "".join(cur_sentences)
            prefix = f"{doc_id}_p{page}" if page is not None else doc_id
            cid = f"{prefix}_c{chunk_index}"
            start_pos = text.find(content, max(0, char_offset - 200))
            if start_pos == -1:
                start_pos = char_offset
            end_pos = start_pos + len(content)
            char_offset = end_pos

            chunks.append(DocumentChunk(
                chunk_id=cid,
                content=content,
                doc_name=doc_name,
                doc_id=doc_id,
                page=page,
                char_start=start_pos,
                char_end=end_pos,
            ))
            chunk_index += 1

            overlap_sentences = []
            overlap_len = 0
            for back_s in reversed(cur_sentences):
                if overlap_len + len(back_s) <= overlap:
                    overlap_sentences.insert(0, back_s)
                    overlap_len += len(back_s)
                else:
                    break
            cur_sentences = overlap_sentences
            cur_len = overlap_len

        cur_sentences.append(s)
        cur_len += s_len

    if cur_sentences:
        content = "".join(cur_sentences)
        prefix = f"{doc_id}_p{page}" if page is not None else doc_id
        cid = f"{prefix}_c{chunk_index}"
        start_pos = text.find(content, max(0, char_offset - 200))
        if start_pos == -1:
            start_pos = char_offset
        end_pos = start_pos + len(content)

        chunks.append(DocumentChunk(
            chunk_id=cid,
            content=content,
            doc_name=doc_name,
            doc_id=doc_id,
            page=page,
            char_start=start_pos,
            char_end=end_pos,
        ))

    return chunks


def chunk_document_pages(
    pages: List[Dict[str, Any]],
    doc_name: str = "document.pdf",
    doc_id: str = "doc_1",
    chunk_size: int = 250,
    overlap: int = 40,
) -> List[DocumentChunk]:
    """
    按页面进行片段切分，保留准确页码和编号
    """
    all_chunks: List[DocumentChunk] = []
    chunk_index = 1
    for page_item in pages:
        p_num = page_item.get("page", 1)
        p_text = page_item.get("text", "")
        if not p_text.strip():
            continue
        p_chunks = chunk_document_text(
            text=p_text,
            doc_name=doc_name,
            doc_id=doc_id,
            page=p_num,
            chunk_size=chunk_size,
            overlap=overlap,
        )
        for c in p_chunks:
            c.chunk_id = f"{doc_id}_p{p_num}_c{chunk_index}"
            chunk_index += 1
            all_chunks.append(c)
    return all_chunks


if __name__ == "__main__":
    from prompt import SYSTEM_PROMPT
    llm = LLMClient()
    extractor = MatterExtractor(llm, SYSTEM_PROMPT)
    print("extractor ready")