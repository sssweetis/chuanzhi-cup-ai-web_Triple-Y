# -*- coding: utf-8 -*-
"""
通知事项结构化提取系统（文字版）

支持：纯文本通知 → LLM 解析 → 结构化 Matter JSON → DDL 提醒调度

========================= 生产环境清理清单 =========================
本文件中所有 mock 相关代码均带有 [MOCK] 前缀标记。
上线前按以下步骤清理：

  Step 1. 删除末尾 "[MOCK BLOCK START]" 到 "[MOCK BLOCK END]" 之间的全部代码
  Step 2. 删除 LLMClient.extract 中所有 [MOCK-FALLBACK] 标记的分支
  Step 3. 删除常量 LLM_ENABLE_MOCK 及其读取逻辑（[MOCK-SWITCH] 标记）

上线后自检命令：
    grep -n "\\[MOCK" notification_extractor.py
    应无任何输出

未来接入图片 / PDF / 链接：
    见 MatterExtractor.process() 里的 [PREPROCESSOR-HOOK] 标记处
===================================================================
"""

import json
import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

try:
    from jsonschema import validate, ValidationError
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


# ==================== 全局配置 ====================

TZ = timezone(timedelta(hours=8))  # Asia/Shanghai

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("notification_extractor")

# [MOCK-SWITCH] 生产环境删除此常量及其读取逻辑
# 开发阶段：export LLM_ENABLE_MOCK=1 即可在无 API key 时走 mock
LLM_ENABLE_MOCK: bool = os.getenv("LLM_ENABLE_MOCK", "0") == "1"


# ==================== 枚举 ====================

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


# ==================== 工具函数 ====================

def _safe_list(v: Any) -> List:
    """保证返回 list；非 list 一律返回 []"""
    return v if isinstance(v, list) else []


def _safe_dict(v: Any) -> Optional[Dict]:
    """保证返回 dict 或 None"""
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


# ==================== 数据模型 ====================

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
        for k in ["doc_id", "doc_version", "page", "anchor_id",
                  "char_start", "char_end", "chunk_id", "bbox"]:
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
class Reminder:
    reminder_id: str
    offset_minutes: int = 120
    channels: List[str] = field(default_factory=lambda: ["app"])
    enabled: bool = True
    recipients: List[str] = field(default_factory=list)
    repeat: Optional[str] = None
    calendar_uid: Optional[str] = None

    def to_dict(self) -> Dict:
        result = {
            "reminder_id": self.reminder_id,
            "offset_minutes": self.offset_minutes,
            "channels": self.channels,
            "enabled": self.enabled,
        }
        if self.recipients:
            result["recipients"] = self.recipients
        if self.repeat:
            result["repeat"] = self.repeat
        if self.calendar_uid:
            result["calendar_uid"] = self.calendar_uid
        return result

    @classmethod
    def from_dict(cls, d: Dict) -> "Reminder":
        return cls(
            reminder_id=_safe_str(d.get("reminder_id")) or f"rem_{uuid.uuid4().hex[:6]}",
            offset_minutes=d.get("offset_minutes", 120),
            channels=_safe_list(d.get("channels")) or ["app"],
            enabled=bool(d.get("enabled", True)),
            recipients=_safe_list(d.get("recipients")),
            repeat=d.get("repeat"),
            calendar_uid=d.get("calendar_uid"),
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
        if self.start_at:
            result["start_at"] = self.start_at
        if self.due_at:
            result["due_at"] = self.due_at
        if self.end_at:
            result["end_at"] = self.end_at
        if self.source_ref:
            result["source_ref"] = self.source_ref.to_dict()
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
    address: Optional[str] = None
    room: Optional[str] = None
    url: Optional[str] = None
    map_url: Optional[str] = None
    source_ref: Optional[SourceRef] = None

    def to_dict(self) -> Dict:
        result = {"type": self.type}
        for k in ["name", "address", "room", "url", "map_url"]:
            v = getattr(self, k)
            if v:
                result[k] = v
        if self.source_ref:
            result["source_ref"] = self.source_ref.to_dict()
        return result

    @classmethod
    def from_dict(cls, d: Dict) -> "Location":
        src = _safe_dict(d.get("source_ref"))
        return cls(
            type=_safe_str(d.get("type"), "offline"),
            name=d.get("name"),
            address=d.get("address"),
            room=d.get("room"),
            url=d.get("url"),
            map_url=d.get("map_url"),
            source_ref=SourceRef.from_dict(src) if src else None,
        )


@dataclass
class Attachment:
    attachment_id: str
    attachment_name: str
    attachment_type: str = "file"
    attachment_url: Optional[str] = None
    mime_type: Optional[str] = None
    size: Optional[int] = None
    checksum: Optional[str] = None
    access_level: str = "public"
    expire_at: Optional[str] = None
    source_ref: Optional[SourceRef] = None

    def to_dict(self) -> Dict:
        result = {
            "attachment_id": self.attachment_id,
            "attachment_name": self.attachment_name,
            "attachment_type": self.attachment_type,
        }
        for k in ["attachment_url", "mime_type", "size", "checksum", "access_level", "expire_at"]:
            v = getattr(self, k)
            if v is not None:
                result[k] = v
        if self.source_ref:
            result["source_ref"] = self.source_ref.to_dict()
        return result

    @classmethod
    def from_dict(cls, d: Dict) -> "Attachment":
        src = _safe_dict(d.get("source_ref"))
        return cls(
            attachment_id=_safe_str(d.get("attachment_id")) or f"att_{uuid.uuid4().hex[:6]}",
            attachment_name=_safe_str(d.get("attachment_name")),
            attachment_type=_safe_str(d.get("attachment_type"), "file"),
            attachment_url=d.get("attachment_url"),
            mime_type=d.get("mime_type"),
            size=d.get("size"),
            checksum=d.get("checksum"),
            access_level=_safe_str(d.get("access_level"), "public"),
            expire_at=d.get("expire_at"),
            source_ref=SourceRef.from_dict(src) if src else None,
        )


@dataclass
class Material:
    material_id: str
    material_name: str
    material_desc: Optional[str] = None
    required_by_source: bool = False
    material_type: str = "unspecified"
    status: str = "pending"
    template_attachment_id: Optional[str] = None
    submitted_attachment_ids: List[str] = field(default_factory=list)
    review_status: Optional[str] = None
    source_ref: Optional[SourceRef] = None

    def to_dict(self) -> Dict:
        result = {
            "material_id": self.material_id,
            "material_name": self.material_name,
            "material_type": self.material_type,
            "status": self.status,
        }
        if self.material_desc:
            result["material_desc"] = self.material_desc
        if self.required_by_source:
            result["required_by_source"] = True
        if self.template_attachment_id:
            result["template_attachment_id"] = self.template_attachment_id
        if self.submitted_attachment_ids:
            result["submitted_attachment_ids"] = self.submitted_attachment_ids
        if self.review_status:
            result["review_status"] = self.review_status
        if self.source_ref:
            result["source_ref"] = self.source_ref.to_dict()
        return result

    @classmethod
    def from_dict(cls, d: Dict) -> "Material":
        src = _safe_dict(d.get("source_ref"))
        return cls(
            material_id=_safe_str(d.get("material_id")) or f"mat_{uuid.uuid4().hex[:6]}",
            material_name=_safe_str(d.get("material_name")),
            material_desc=d.get("material_desc"),
            required_by_source=bool(d.get("required_by_source", False)),
            material_type=_safe_str(d.get("material_type"), "unspecified"),
            status=_safe_str(d.get("status"), "pending"),
            template_attachment_id=d.get("template_attachment_id"),
            submitted_attachment_ids=_safe_list(d.get("submitted_attachment_ids")),
            review_status=d.get("review_status"),
            source_ref=SourceRef.from_dict(src) if src else None,
        )


@dataclass
class Review:
    required: bool = False
    reviewer: Optional[Dict] = None
    status: Optional[str] = None

    def to_dict(self) -> Dict:
        result = {"required": self.required}
        if self.reviewer:
            result["reviewer"] = self.reviewer
        if self.status:
            result["status"] = self.status
        return result

    @classmethod
    def from_dict(cls, d: Dict) -> "Review":
        return cls(
            required=bool(d.get("required", False)),
            reviewer=_safe_dict(d.get("reviewer")),
            status=d.get("status"),
        )


@dataclass
class Step:
    """
    步骤（支持递归）。
    通过 is_sub_step 区分层级：
      - is_sub_step=False → 输出 step_id
      - is_sub_step=True  → 输出 sub_step_id
    """
    step_id: str
    order: int
    title: str
    desc: Optional[str] = None
    status: str = "not_started"
    parent_id: Optional[str] = None
    is_sub_step: bool = False

    start_at: Optional[str] = None
    due_at: Optional[str] = None
    due_at_inherited_from: Optional[str] = None
    reminders: List[Reminder] = field(default_factory=list)
    location: Optional[Location] = None
    key_points: List[str] = field(default_factory=list)
    materials: List[str] = field(default_factory=list)
    attachments: List[str] = field(default_factory=list)
    dependencies: List[Dict] = field(default_factory=list)
    parallel: bool = False
    condition: Optional[str] = None
    owner: Optional[Dict] = None
    assignees: List[Dict] = field(default_factory=list)
    review: Optional[Review] = None
    sub_step_list: List["Step"] = field(default_factory=list)
    source_ref: Optional[SourceRef] = None

    def to_dict(self) -> Dict:
        # 按层级选择 ID 键名
        id_key = "sub_step_id" if self.is_sub_step else "step_id"
        result: Dict[str, Any] = {
            id_key: self.step_id,
            "order": self.order,
            "title": self.title,
            "status": self.status,
        }
        if self.parent_id:
            result["parent_id"] = self.parent_id
        if self.desc:
            result["desc"] = self.desc
        if self.start_at:
            result["start_at"] = self.start_at
        if self.due_at:
            result["due_at"] = self.due_at
        if self.due_at_inherited_from:
            result["due_at_inherited_from"] = self.due_at_inherited_from
        if self.reminders:
            result["reminders"] = [r.to_dict() for r in self.reminders]
        if self.location:
            result["location"] = self.location.to_dict()
        if self.key_points:
            result["key_points"] = self.key_points
        if self.materials:
            result["materials"] = self.materials
        if self.attachments:
            result["attachments"] = self.attachments
        if self.dependencies:
            result["dependencies"] = self.dependencies
        if self.parallel:
            result["parallel"] = True
        if self.condition:
            result["condition"] = self.condition
        if self.owner:
            result["owner"] = self.owner
        if self.assignees:
            result["assignees"] = self.assignees
        if self.review:
            result["review"] = self.review.to_dict()
        if self.sub_step_list:
            result["sub_step_list"] = [s.to_dict() for s in self.sub_step_list]
        if self.source_ref:
            result["source_ref"] = self.source_ref.to_dict()
        return result

    @classmethod
    def from_dict(cls, d: Dict, is_sub_step: bool = False) -> "Step":
        src = _safe_dict(d.get("source_ref"))
        loc = _safe_dict(d.get("location"))
        rev = _safe_dict(d.get("review"))

        # 兼容两种 ID 键名
        sid = d.get("sub_step_id") if is_sub_step else d.get("step_id")
        if not sid:
            sid = d.get("step_id") or d.get("sub_step_id")
        if not sid:
            sid = (f"sub_{uuid.uuid4().hex[:6]}"
                   if is_sub_step else f"step_{uuid.uuid4().hex[:6]}")

        return cls(
            step_id=_safe_str(sid),
            order=int(d.get("order", 1)),
            title=_safe_str(d.get("title")),
            desc=d.get("desc"),
            status=normalize_enum(d.get("status"), Status, "not_started"),
            parent_id=d.get("parent_id"),
            is_sub_step=is_sub_step,
            start_at=d.get("start_at") if is_valid_iso(d.get("start_at")) else None,
            due_at=d.get("due_at") if is_valid_iso(d.get("due_at")) else None,
            due_at_inherited_from=d.get("due_at_inherited_from"),
            reminders=[Reminder.from_dict(r) for r in _safe_list(d.get("reminders"))],
            location=Location.from_dict(loc) if loc else None,
            key_points=_safe_list(d.get("key_points")),
            materials=_safe_list(d.get("materials")),
            attachments=_safe_list(d.get("attachments")),
            dependencies=_safe_list(d.get("dependencies")),
            parallel=bool(d.get("parallel", False)),
            condition=d.get("condition"),
            owner=_safe_dict(d.get("owner")),
            assignees=_safe_list(d.get("assignees")),
            review=Review.from_dict(rev) if rev else None,
            sub_step_list=[
                Step.from_dict(s, is_sub_step=True)
                for s in _safe_list(d.get("sub_step_list"))
            ],
            source_ref=SourceRef.from_dict(src) if src else None,
        )


@dataclass
class Warning:
    warning_id: str
    warning_type: str
    mode_scope: str = "complex"
    severity: str = "medium"
    message: Optional[str] = None
    rule: Dict = field(default_factory=dict)
    action: Dict = field(default_factory=dict)
    related_refs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        result = {
            "warning_id": self.warning_id,
            "warning_type": self.warning_type,
            "mode_scope": self.mode_scope,
            "severity": self.severity,
        }
        if self.message:
            result["message"] = self.message
        if self.rule:
            result["rule"] = self.rule
        if self.action:
            result["action"] = self.action
        if self.related_refs:
            result["related_refs"] = self.related_refs
        return result

    @classmethod
    def from_dict(cls, d: Dict) -> "Warning":
        return cls(
            warning_id=_safe_str(d.get("warning_id")) or f"warn_{uuid.uuid4().hex[:6]}",
            warning_type=_safe_str(d.get("warning_type")),
            mode_scope=_safe_str(d.get("mode_scope"), "complex"),
            severity=_safe_str(d.get("severity"), "medium"),
            message=d.get("message"),
            rule=_safe_dict(d.get("rule")) or {},
            action=_safe_dict(d.get("action")) or {},
            related_refs=_safe_list(d.get("related_refs")),
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
    target: Optional[Dict] = None
    background: Optional[str] = None
    category: Optional[str] = None
    priority: str = "medium"
    tags: List[str] = field(default_factory=list)
    status: str = "not_started"
    status_source: str = "auto"
    timezone: str = "Asia/Shanghai"
    created_at: str = ""
    updated_at: str = ""

    owner: Optional[Dict] = None
    assignees: List[Dict] = field(default_factory=list)
    participants: List[Dict] = field(default_factory=list)
    contact: Optional[Dict] = None

    deadline: Optional[Deadline] = None
    reminders: List[Reminder] = field(default_factory=list)
    recurrence: Optional[Dict] = None

    default_location: Optional[Location] = None
    key_points: List[str] = field(default_factory=list)
    attachments: List[Attachment] = field(default_factory=list)
    materials: List[Material] = field(default_factory=list)
    step_list: List[Step] = field(default_factory=list)
    warning_list: List[Warning] = field(default_factory=list)

    permissions: Optional[Dict] = None
    audit_log: List[Dict] = field(default_factory=list)
    comments: List[Dict] = field(default_factory=list)

    sources: List[SourceRef] = field(default_factory=list)

    def to_dict(self) -> Dict:
        result = {
            "schema_version": self.schema_version,
            "id": self.id,
            "mode": self.mode,
            "mode_source": self.mode_source,
            "complexity_score": self.complexity_score,
            "title": self.title,
            "priority": self.priority,
            "status": self.status,
            "status_source": self.status_source,
            "timezone": self.timezone,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.detected_features:
            result["detected_features"] = self.detected_features
        if self.enabled_sections:
            result["enabled_sections"] = self.enabled_sections
        if self.target:
            result["target"] = self.target
        if self.background:
            result["background"] = self.background
        if self.category:
            result["category"] = self.category
        if self.tags:
            result["tags"] = self.tags
        if self.owner:
            result["owner"] = self.owner
        if self.assignees:
            result["assignees"] = self.assignees
        if self.participants:
            result["participants"] = self.participants
        if self.contact:
            result["contact"] = self.contact
        if self.deadline:
            result["deadline"] = self.deadline.to_dict()
        if self.reminders:
            result["reminders"] = [r.to_dict() for r in self.reminders]
        if self.recurrence:
            result["recurrence"] = self.recurrence
        if self.default_location:
            result["default_location"] = self.default_location.to_dict()
        if self.key_points:
            result["key_points"] = self.key_points
        if self.attachments:
            result["attachments"] = [a.to_dict() for a in self.attachments]
        if self.materials:
            result["materials"] = [m.to_dict() for m in self.materials]
        if self.step_list:
            result["step_list"] = [s.to_dict() for s in self.step_list]
        if self.warning_list:
            result["warning_list"] = [w.to_dict() for w in self.warning_list]
        if self.permissions:
            result["permissions"] = self.permissions
        if self.audit_log:
            result["audit_log"] = self.audit_log
        if self.comments:
            result["comments"] = self.comments
        if self.sources:
            result["sources"] = [s.to_dict() for s in self.sources]
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
        m.target = _safe_dict(d.get("target"))
        m.background = d.get("background")
        m.category = d.get("category")
        m.priority = normalize_enum(d.get("priority"), Priority, "medium")
        m.tags = _safe_list(d.get("tags"))
        m.status = normalize_enum(d.get("status"), Status, "not_started")
        m.status_source = _safe_str(d.get("status_source"), "auto")
        m.timezone = _safe_str(d.get("timezone"), "Asia/Shanghai")
        m.created_at = _safe_str(d.get("created_at"))
        m.updated_at = _safe_str(d.get("updated_at"))

        m.owner = _safe_dict(d.get("owner"))
        m.assignees = _safe_list(d.get("assignees"))
        m.participants = _safe_list(d.get("participants"))
        m.contact = _safe_dict(d.get("contact"))

        if _safe_dict(d.get("deadline")):
            m.deadline = Deadline.from_dict(d["deadline"])
        m.reminders = [Reminder.from_dict(r) for r in _safe_list(d.get("reminders"))]
        m.recurrence = _safe_dict(d.get("recurrence"))

        if _safe_dict(d.get("default_location")):
            m.default_location = Location.from_dict(d["default_location"])
        m.key_points = _safe_list(d.get("key_points"))
        m.attachments = [Attachment.from_dict(a) for a in _safe_list(d.get("attachments"))]
        m.materials = [Material.from_dict(x) for x in _safe_list(d.get("materials"))]
        m.step_list = [
            Step.from_dict(s, is_sub_step=False)
            for s in _safe_list(d.get("step_list"))
        ]
        m.warning_list = [Warning.from_dict(w) for w in _safe_list(d.get("warning_list"))]

        m.permissions = _safe_dict(d.get("permissions"))
        m.audit_log = _safe_list(d.get("audit_log"))
        m.comments = _safe_list(d.get("comments"))

        m.sources = [SourceRef.from_dict(s) for s in _safe_list(d.get("sources"))]
        return m


# ==================== 模式裁剪与字段互斥 ====================

MODE_FORBIDDEN_FIELDS = {
    "simple": {
        "owner", "assignees", "participants", "contact",
        "default_location", "key_points", "attachments",
        "materials", "step_list", "warning_list",
        "permissions", "audit_log", "comments", "recurrence",
    },
    "standard": {"recurrence", "permissions", "audit_log", "comments"},
    "complex": set(),
}

MODE_ALLOWED_SECTIONS = {
    "simple": ["summary", "schedule", "source"],
    "standard": ["summary", "schedule", "content", "steps", "materials", "source"],
    "complex": ["summary", "schedule", "content", "steps",
                "materials", "warnings", "governance", "source"],
}

STEP_FORBIDDEN_IN_NON_COMPLEX = {
    "sub_step_list", "dependencies", "parallel",
    "condition", "review", "owner", "assignees",
    "start_at", "reminders",
}

STANDARD_WARNING_TYPES = {"deadline_risk", "missing_material"}


def enforce_mode(raw: Dict) -> Dict:
    """按 mode 裁剪字段；LLM 输出脏字段也能被兜底裁掉"""
    if not isinstance(raw, dict):
        return raw
    mode = raw.get("mode", "simple")
    if mode not in MODE_FORBIDDEN_FIELDS:
        mode = "simple"
        raw["mode"] = mode

    for f in MODE_FORBIDDEN_FIELDS[mode]:
        raw.pop(f, None)

    if mode in ("simple", "standard"):
        for step in _safe_list(raw.get("step_list")):
            if not isinstance(step, dict):
                continue
            for f in STEP_FORBIDDEN_IN_NON_COMPLEX:
                step.pop(f, None)
            for sub in _safe_list(step.get("sub_step_list")):
                if isinstance(sub, dict):
                    for f in STEP_FORBIDDEN_IN_NON_COMPLEX:
                        sub.pop(f, None)

    if mode == "standard":
        raw["warning_list"] = [
            w for w in _safe_list(raw.get("warning_list"))
            if isinstance(w, dict) and w.get("warning_type") in STANDARD_WARNING_TYPES
        ]
        if not raw["warning_list"]:
            raw.pop("warning_list", None)

    return raw


def enforce_enabled_sections(raw: Dict) -> Dict:
    if not isinstance(raw, dict):
        return raw
    mode = raw.get("mode", "simple")
    raw["enabled_sections"] = MODE_ALLOWED_SECTIONS.get(
        mode, MODE_ALLOWED_SECTIONS["simple"]
    )
    return raw


# ==================== 复杂度重算 ====================

FEATURE_WEIGHTS = {
    "has_deadline": 0.2,
    "has_multiple_reminders": 0.1,
    "has_multiple_steps": 0.2,
    "has_sub_steps": 0.1,
    "has_materials": 0.2,
    "has_review": 0.1,
    "has_dependencies": 0.1,
    "has_recurrence": 0.1,
}


def recompute_complexity(features: List[str]) -> float:
    return min(1.0, sum(FEATURE_WEIGHTS.get(f, 0.0) for f in features))


def decide_mode(features: List[str], score: float) -> str:
    if any(f in features for f in ("has_sub_steps", "has_review", "has_dependencies")):
        return "complex"
    if score < 0.3:
        return "simple"
    if score <= 0.6:
        return "standard"
    return "complex"


# ==================== JSON Schema ====================

MATTER_SCHEMA = {
    "type": "object",
    "required": ["schema_version", "id", "mode", "title", "status"],
    "properties": {
        "schema_version": {"type": "string"},
        "id": {"type": "string"},
        "mode": {"enum": ["simple", "standard", "complex"]},
        "mode_source": {"enum": ["auto", "user"]},
        "complexity_score": {"type": "number", "minimum": 0, "maximum": 1},
        "detected_features": {"type": "array", "items": {"type": "string"}},
        "enabled_sections": {"type": "array", "items": {"type": "string"}},
        "title": {"type": "string"},
        "priority": {"enum": ["low", "medium", "high", "urgent"]},
        "status": {
            "enum": [
                "not_started", "in_progress", "completed", "cancelled",
                "skipped", "failed", "delayed", "pending_review",
                "submitted", "need_resubmit",
            ]
        },
        "timezone": {"type": "string"},
        "deadline": {"type": ["object", "null"]},
        "step_list": {"type": "array"},
        "materials": {"type": "array"},
        "attachments": {"type": "array"},
        "warning_list": {"type": "array"},
        "sources": {"type": "array"},
    },
}


def validate_matter(data: Dict) -> Tuple[bool, Optional[str]]:
    if not HAS_JSONSCHEMA:
        logger.warning("jsonschema 未安装，跳过校验（建议 pip install jsonschema）")
        return True, None
    try:
        validate(instance=data, schema=MATTER_SCHEMA)
        return True, None
    except ValidationError as e:
        return False, str(e)


# ==================== LLM 调用 ====================

class LLMClient:
    """LLM 调用客户端（OpenAI 兼容接口）"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 60,
    ):
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.base_url = base_url or os.getenv(
            "LLM_BASE_URL", "https://api.openai.com/v1"
        )
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o")
        self.timeout = timeout

    def extract(self, notification_text: str, system_prompt: str) -> Dict:
        """
        把一段通知文本交给 LLM，返回解析后的 JSON 字典。

        生产路径：调用真 LLM API
        开发路径：当 LLM_ENABLE_MOCK=1 且无 API key 或调用失败时降级到 mock
        """
        request_id = uuid.uuid4().hex[:8]
        logger.info(
            "[%s] 开始解析：model=%s，文本长度=%d",
            request_id, self.model, len(notification_text),
        )

        # ---- 构造 messages ----
        now_str = datetime.now(TZ).isoformat()
        system_content = system_prompt.replace("{{NOW}}", now_str)
        system_content = system_content.replace("{{USER_NOTIFICATION_TEXT}}", "")

        # ---- 生产路径：真 API ----
        if not self.api_key:
            # [MOCK-FALLBACK] 生产环境删除整个 if 分支，改为直接抛 RuntimeError
            if LLM_ENABLE_MOCK:
                logger.warning("[%s] LLM_API_KEY 未配置，降级到 mock", request_id)
                return self._mock_extract(notification_text)
            raise RuntimeError("LLM_API_KEY 未配置，无法解析通知")

        try:
            from openai import OpenAI
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
            )
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": notification_text},
                ],
                temperature=0,
                response_format={"type": "json_object"},
            )
            raw_text = response.choices[0].message.content
            raw = json.loads(raw_text)
            if response.usage:
                logger.info(
                    "[%s] API 完成：prompt=%d，completion=%d，mode=%s",
                    request_id,
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                    raw.get("mode"),
                )
            return raw

        except Exception as e:
            logger.exception("[%s] LLM 调用失败：%s", request_id, e)
            # [MOCK-FALLBACK] 生产环境删除整个 if 分支，改为直接 raise
            if LLM_ENABLE_MOCK:
                logger.warning("[%s] 降级到 mock", request_id)
                return self._mock_extract(notification_text)
            raise

    # ==================== [MOCK BLOCK START] ====================
    # 以下代码仅用于开发/测试阶段。生产环境请整块删除。
    # 删除步骤见文件顶部“生产环境清理清单”。

    def _mock_extract(self, text: str) -> Dict:
        if ("流程" in text or "审核" in text
                or "缴费" in text or "准考证" in text):
            return self._mock_complex(text)
        if "提交" in text and ("材料" in text or "附件" in text
                               or "地点" in text or "行政楼" in text):
            return self._mock_standard(text)
        return self._mock_simple(text)

    def _mock_simple(self, text: str) -> Dict:
        return {
            "schema_version": "1.0",
            "id": "matter_auto",
            "mode": "simple",
            "mode_source": "auto",
            "complexity_score": 0.2,
            "detected_features": ["has_deadline"],
            "enabled_sections": ["summary", "schedule", "source"],
            "title": "提交奖学金报名表",
            "priority": "medium",
            "status": "not_started",
            "status_source": "auto",
            "timezone": "Asia/Shanghai",
            "created_at": "",
            "updated_at": "",
            "deadline": {
                "scope": "overall",
                "label": "截止时间",
                "due_at": "2026-10-25T18:00:00+08:00",
                "all_day": False,
                "source_ref": {"quote": text},
            },
            "reminders": [{
                "reminder_id": "rem_1",
                "offset_minutes": 120,
                "channels": ["app"],
                "enabled": True,
            }],
            "sources": [{"quote": text, "page": None}],
        }

    def _mock_standard(self, text: str) -> Dict:
        return {
            "schema_version": "1.0",
            "id": "matter_auto",
            "mode": "standard",
            "mode_source": "auto",
            "complexity_score": 0.5,
            "detected_features": [
                "has_deadline", "has_multiple_steps",
                "has_materials", "has_attachments", "has_location",
            ],
            "enabled_sections": [
                "summary", "schedule", "content",
                "steps", "materials", "source",
            ],
            "title": "奖学金报名材料提交",
            "priority": "medium",
            "status": "not_started",
            "status_source": "auto",
            "timezone": "Asia/Shanghai",
            "created_at": "",
            "updated_at": "",
            "deadline": {
                "scope": "overall",
                "label": "截止时间",
                "due_at": "2026-10-25T18:00:00+08:00",
                "all_day": False,
                "source_ref": {"quote": "10月25日18:00前提交"},
            },
            "reminders": [{
                "reminder_id": "rem_1",
                "offset_minutes": 120,
                "channels": ["app"],
                "enabled": True,
            }],
            "default_location": {
                "type": "offline",
                "name": "行政楼302",
                "room": "302",
                "source_ref": {"quote": "交至行政楼302"},
            },
            "key_points": ["需本人签字"],
            "attachments": [{
                "attachment_id": "att_1",
                "attachment_name": "报名表",
                "attachment_type": "file",
                "source_ref": {"quote": "附件1"},
            }],
            "materials": [
                {
                    "material_id": "mat_1",
                    "material_name": "报名表",
                    "material_type": "required",
                    "status": "pending",
                    "template_attachment_id": "att_1",
                    "source_ref": {"quote": "提交报名表（附件1）"},
                },
                {
                    "material_id": "mat_2",
                    "material_name": "成绩单",
                    "material_type": "required",
                    "status": "pending",
                    "source_ref": {"quote": "成绩单"},
                },
                {
                    "material_id": "mat_3",
                    "material_name": "身份证复印件",
                    "material_type": "required",
                    "status": "pending",
                    "source_ref": {"quote": "身份证复印件"},
                },
            ],
            "step_list": [
                {
                    "step_id": "step_1",
                    "order": 1,
                    "title": "准备报名材料",
                    "status": "not_started",
                    "due_at": "2026-10-25T18:00:00+08:00",
                    "due_at_inherited_from": "overall",
                    "key_points": ["需本人签字"],
                    "materials": ["mat_1", "mat_2", "mat_3"],
                    "attachments": ["att_1"],
                    "source_ref": {
                        "quote": "提交报名表（附件1）、成绩单、身份证复印件"
                    },
                },
                {
                    "step_id": "step_2",
                    "order": 2,
                    "title": "交至行政楼302",
                    "status": "not_started",
                    "due_at": "2026-10-25T18:00:00+08:00",
                    "due_at_inherited_from": "overall",
                    "location": {
                        "type": "offline",
                        "name": "行政楼302",
                        "room": "302",
                    },
                    "source_ref": {"quote": "交至行政楼302"},
                },
            ],
            "sources": [{"quote": text, "page": None}],
        }

    def _mock_complex(self, text: str) -> Dict:
        return {
            "schema_version": "1.0",
            "id": "matter_auto",
            "mode": "complex",
            "mode_source": "auto",
            "complexity_score": 0.9,
            "detected_features": [
                "has_deadline", "has_multiple_steps", "has_sub_steps",
                "has_materials", "has_attachments", "has_review",
                "has_dependencies",
            ],
            "enabled_sections": [
                "summary", "schedule", "content", "steps",
                "materials", "warnings", "governance", "source",
            ],
            "title": "奖学金报名流程",
            "priority": "medium",
            "status": "not_started",
            "status_source": "auto",
            "timezone": "Asia/Shanghai",
            "created_at": "",
            "updated_at": "",
            "deadline": {
                "scope": "overall",
                "label": "截止时间",
                "start_at": "2026-10-20T00:00:00+08:00",
                "due_at": "2026-11-01T23:59:59+08:00",
                "source_ref": {"quote": "10月20日-25日在线填写报名表"},
            },
            "reminders": [{
                "reminder_id": "rem_1",
                "offset_minutes": 120,
                "channels": ["app"],
                "enabled": True,
            }],
            "attachments": [{
                "attachment_id": "att_1",
                "attachment_name": "报名表",
                "attachment_type": "file",
                "source_ref": {"quote": "附件1"},
            }],
            "materials": [
                {
                    "material_id": "mat_1",
                    "material_name": "报名表",
                    "material_type": "required",
                    "status": "pending",
                    "template_attachment_id": "att_1",
                    "source_ref": {"quote": "在线填写报名表（附件1）"},
                },
                {
                    "material_id": "mat_2",
                    "material_name": "身份证",
                    "material_type": "required",
                    "status": "pending",
                    "source_ref": {"quote": "上传身份证"},
                },
                {
                    "material_id": "mat_3",
                    "material_name": "成绩单",
                    "material_type": "required",
                    "status": "pending",
                    "source_ref": {"quote": "上传成绩单"},
                },
            ],
            "step_list": [
                {
                    "step_id": "step_1",
                    "order": 1,
                    "title": "在线填写报名表",
                    "status": "not_started",
                    "start_at": "2026-10-20T00:00:00+08:00",
                    "due_at": "2026-10-25T23:59:59+08:00",
                    "materials": ["mat_1"],
                    "attachments": ["att_1"],
                    "sub_step_list": [
                        {
                            "sub_step_id": "sub_1_1",
                            "parent_id": "step_1",
                            "order": 1,
                            "title": "下载报名表模板",
                            "status": "not_started",
                            "source_ref": {"quote": "附件1"},
                        },
                        {
                            "sub_step_id": "sub_1_2",
                            "parent_id": "step_1",
                            "order": 2,
                            "title": "填写并上传",
                            "status": "not_started",
                            "source_ref": {"quote": "在线填写报名表"},
                        },
                    ],
                    "source_ref": {
                        "quote": "10月20日-25日在线填写报名表（附件1）"
                    },
                },
                {
                    "step_id": "step_2",
                    "order": 2,
                    "title": "材料审核",
                    "status": "not_started",
                    "start_at": "2026-10-26T00:00:00+08:00",
                    "due_at": "2026-10-28T23:59:59+08:00",
                    "owner": {"name": "王老师"},
                    "review": {
                        "required": True,
                        "reviewer": {"name": "王老师"},
                        "status": "pending",
                    },
                    "dependencies": [
                        {"type": "finish_to_start", "step_id": "step_1"}
                    ],
                    "source_ref": {"quote": "10月26-28日王老师审核"},
                },
                {
                    "step_id": "step_3",
                    "order": 3,
                    "title": "缴费",
                    "status": "not_started",
                    "start_at": "2026-10-29T00:00:00+08:00",
                    "due_at": "2026-10-30T23:59:59+08:00",
                    "condition": "审核通过后",
                    "dependencies": [
                        {"type": "finish_to_start", "step_id": "step_2"}
                    ],
                    "source_ref": {"quote": "10月29-30日缴费100元"},
                },
                {
                    "step_id": "step_4",
                    "order": 4,
                    "title": "打印准考证",
                    "status": "not_started",
                    "start_at": "2026-11-01T00:00:00+08:00",
                    "due_at": "2026-11-01T23:59:59+08:00",
                    "dependencies": [
                        {"type": "finish_to_start", "step_id": "step_3"}
                    ],
                    "source_ref": {"quote": "11月1日打印准考证"},
                },
            ],
            "warning_list": [{
                "warning_id": "warn_1",
                "warning_type": "deadline_risk",
                "mode_scope": "complex",
                "severity": "medium",
                "message": "步骤3缴费与步骤2审核间隔仅1天，请提前准备",
                "rule": {"related_step_ids": ["step_2", "step_3"]},
                "action": {
                    "type": "notify",
                    "suggestion": "建议审核通过后立即缴费",
                },
            }],
            "sources": [{"quote": text, "page": None}],
        }

    # ==================== [MOCK BLOCK END] ====================


# ==================== 提醒调度 ====================

@dataclass
class ScheduledReminder:
    matter_id: str
    title: str
    fire_at: datetime
    channels: List[str]
    payload: Dict


class ReminderScheduler:
    """按 deadline.due_at - offset_minutes 生成提醒任务"""

    def __init__(self):
        self.jobs: List[ScheduledReminder] = []

    def schedule_from_matter(self, matter: Matter) -> List[ScheduledReminder]:
        jobs: List[ScheduledReminder] = []
        if not matter.deadline or not matter.deadline.due_at:
            return jobs

        due = parse_iso(matter.deadline.due_at)
        if not due:
            logger.warning("matter %s 的 due_at 非法，跳过调度", matter.id)
            return jobs

        for r in matter.reminders:
            if not r.enabled:
                continue
            fire_at = due - timedelta(minutes=r.offset_minutes)
            if fire_at <= datetime.now(TZ):
                logger.info("matter %s 提醒时间已过，跳过", matter.id)
                continue
            jobs.append(ScheduledReminder(
                matter_id=matter.id,
                title=matter.title,
                fire_at=fire_at,
                channels=r.channels,
                payload={"reminder_id": r.reminder_id},
            ))
        self.jobs.extend(jobs)
        return jobs

    def pop_due(self, now: Optional[datetime] = None) -> List[ScheduledReminder]:
        now = now or datetime.now(TZ)
        due, just = [], []
        for j in self.jobs:
            (due if j.fire_at <= now else just).append(j)
        self.jobs = just
        return due


# ==================== 主流程 ====================

class MatterExtractor:
    """端到端：文字 → Matter + 已调度提醒"""

    def __init__(self, llm: LLMClient, system_prompt: str):
        self.llm = llm
        self.system_prompt = system_prompt
        self.scheduler = ReminderScheduler()

    def process(self, source: str) -> Tuple[Optional[Matter], Optional[str]]:
        """
        参数：
            source: 通知原文（目前仅支持纯文本）

        [PREPROCESSOR-HOOK]
        未来接入图片 / PDF / 链接时，在这里先调用预处理器把 source 转成文本：
            text = self.preprocessor.to_text(source)
        再往下走。目前直接透传。
        """
        text = source

        # 1. LLM 抽取
        raw = self.llm.extract(text, self.system_prompt)

        # 2. 用公式重算复杂度与模式（不信 LLM 的数字）
        #    注意：这里先 round 再传给 decide_mode，
        #    否则 0.2+0.2+0.2 = 0.6000000000000001 > 0.6 会导致误判为 complex
        features = _safe_list(raw.get("detected_features"))
        score = round(recompute_complexity(features), 3)
        raw["complexity_score"] = score
        raw["mode"] = decide_mode(features, score)

        # 3. 按 mode 裁剪字段（防脏数据）
        raw = enforce_mode(raw)

        # 4. 覆盖 enabled_sections
        raw = enforce_enabled_sections(raw)

        # 5. Schema 校验
        ok, err = validate_matter(raw)
        if not ok:
            logger.error("Schema 校验失败：%s", err)
            return None, f"Schema 校验失败：{err}"

        # 6. 反序列化
        matter = Matter.from_dict(raw)

        # 7. 系统注入
        now_iso = datetime.now(TZ).isoformat()
        matter.created_at = matter.created_at or now_iso
        matter.updated_at = now_iso
        if matter.id == "matter_auto":
            matter.id = f"matter_{uuid.uuid4().hex[:8]}"
        if not matter.title:
            matter.title = (matter.background or "")[:20] or "未命名事项"

        # 8. 调度提醒
        self.scheduler.schedule_from_matter(matter)

        return matter, None


# ==================== Demo ====================

if __name__ == "__main__":
    # 开发阶段：export LLM_ENABLE_MOCK=1
    # 生产/联调：export LLM_API_KEY=sk-xxx，不要设置 LLM_ENABLE_MOCK
    SYSTEM_PROMPT = """
# Role
你是通知事项结构化提取助手。

# 当前时间
NOW = {{NOW}}

# 输出要求
- 严格输出 JSON，不要 Markdown 标记，不要解释
- 原文没有的字段直接省略，不要输出 null 占位
- 空数组 / 空对象一律省略
- 禁止编造原文没有的信息

# 模式
- simple / standard / complex 三选一
- 输出 mode / complexity_score / detected_features / enabled_sections

# 输入通知
{{USER_NOTIFICATION_TEXT}}
"""

    samples = [
        "请于10月25日18:00前提交奖学金报名表。",
        "奖学金报名：10月25日18:00前提交报名表（附件1）、成绩单、"
        "身份证复印件，交至行政楼302，需本人签字。",
        "奖学金报名流程：10月20日-25日在线填写报名表（附件1），"
        "上传身份证和成绩单；10月26-28日王老师审核，审核通过后才能缴费；"
        "10月29-30日缴费100元；11月1日打印准考证。",
    ]

    llm = LLMClient()
    extractor = MatterExtractor(llm, SYSTEM_PROMPT)

    for i, text in enumerate(samples, 1):
        print(f"\n===== 样本 {i} =====")
        print("输入：", text)
        matter, err = extractor.process(text)
        if err:
            print("失败：", err)
            continue
        print(f"mode={matter.mode}  score={matter.complexity_score}  "
              f"sections={matter.enabled_sections}")
        print(json.dumps(matter.to_dict(), ensure_ascii=False, indent=2))

    print("\n===== 已调度提醒 =====")
    for j in extractor.scheduler.jobs:
        print(f"[{j.fire_at.isoformat()}] {j.title} → {j.channels}")