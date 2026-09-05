import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Column, String, Text, DateTime, Float, JSON, ForeignKey, UniqueConstraint, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from apps.api.database import Base


def utcnow():
    # naive UTC：列是 DateTime（无时区），存 aware 会被 asyncpg 拒绝
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(50))  # policy/catalog/faq
    trust_level: Mapped[str] = mapped_column(String(1))  # S/A/B/C
    file_hash: Mapped[str] = mapped_column(String(64), unique=True)
    raw_path: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text, default="")
    valid_from: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    valid_to: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    knowledge_version: Mapped[str] = mapped_column(String(20), default="v1")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column()
    content: Mapped[str] = mapped_column(Text)
    embedding = mapped_column(Vector(384))  # bge-small-zh
    metadata_: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    salt: Mapped[str] = mapped_column(String(32))
    nickname: Mapped[str] = mapped_column(String(50), default="")
    token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PasswordHistory(Base):
    """最近使用过的密码摘要，用于阻止立即复用旧密码。"""

    __tablename__ = "password_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    password_hash: Mapped[str] = mapped_column(String(128))
    salt: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class UserSession(Base):
    """账号登录会话；只保存 token 摘要，支持单独撤销。"""

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_agent: Mapped[str] = mapped_column(String(500), default="")
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class UserAccountLink(Base):
    """已验证的账号关联，供账号切换使用。"""

    __tablename__ = "user_account_links"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "linked_user_id", name="uq_user_account_links_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    linked_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SyncRecord(Base):
    """账号级数据同步检查点。"""

    __tablename__ = "sync_records"
    __table_args__ = (
        UniqueConstraint("user_id", "scope", name="uq_sync_records_user_scope"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    scope: Mapped[str] = mapped_column(String(50))
    version: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/synced/failed
    error: Mapped[str] = mapped_column(Text, default="")
    last_request_id: Mapped[str] = mapped_column(String(64), default="")
    retry_count: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class CacheInvalidation(Base):
    """账号级缓存命名空间失效代次，不删除业务数据。"""

    __tablename__ = "cache_invalidations"
    __table_args__ = (
        UniqueConstraint("user_id", "scope", name="uq_cache_invalidations_user_scope"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    scope: Mapped[str] = mapped_column(String(30))
    generation: Mapped[int] = mapped_column(default=0)
    last_cleared_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Notification(Base):
    """账号级站内通知和投递状态。"""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    channel: Mapped[str] = mapped_column(String(30), default="in_app")
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued/sent/read/failed
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    feedback_type: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    contact: Mapped[str] = mapped_column(String(200), default="")
    attachments: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="received")  # received/in_progress/resolved
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class FeedbackAttachment(Base):
    """反馈附件；以反馈账号为边界保存原始字节和校验摘要。"""

    __tablename__ = "feedback_attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    feedback_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("feedback.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    data: Mapped[bytes] = mapped_column(LargeBinary)
    size_bytes: Mapped[int] = mapped_column()
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class UserAvatar(Base):
    """账号头像原图；后续可在对象存储迁移时替换 data 字段。"""

    __tablename__ = "user_avatars"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    content_type: Mapped[str] = mapped_column(String(50))
    data: Mapped[bytes] = mapped_column(LargeBinary)
    size_bytes: Mapped[int] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    major: Mapped[str] = mapped_column(String(200))
    grade: Mapped[str] = mapped_column(String(20))  # 大一/大二/大三/大四
    campus: Mapped[str] = mapped_column(String(50), default="")  # 仙林/鼓楼/苏州
    interests: Mapped[list] = mapped_column(JSON, default=list)
    strengths: Mapped[list] = mapped_column(JSON, default=list)
    career_goals: Mapped[str] = mapped_column(Text, default="")
    math_willingness: Mapped[bool] = mapped_column(default=False)  # 是否愿意修高数
    campus_flexibility: Mapped[bool] = mapped_column(default=False)  # 是否接受跨校区
    credit_budget: Mapped[int] = mapped_column(default=0)  # 愿意投入的学分数
    certificate_goal: Mapped[str] = mapped_column(String(20), default="")  # degree/cert/none
    schedule_preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class RecommendationReport(Base):
    """保存一次推荐计算的输入快照和结果，支持追溯。"""

    __tablename__ = "recommendation_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    profile_version: Mapped[int] = mapped_column(default=0)
    profile_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    recommendations: Mapped[list] = mapped_column(JSON, default=list)
    is_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LearningPlan(Base):
    """账号级课程规划快照，保存生成结果和用户采用状态。"""

    __tablename__ = "learning_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    program_name: Mapped[str] = mapped_column(String(200))
    profile_version: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft/adopted/archived
    items: Mapped[list] = mapped_column(JSON, default=list)
    alternatives: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    infeasible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    schedule_analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # nullable for backwards compatibility with conversations created before
    # user scoping was introduced; new conversations are always owned by a user.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20))  # user / assistant
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Program(Base):
    __tablename__ = "programs"

    name: Mapped[str] = mapped_column(String(200), primary_key=True)
    total_credits: Mapped[int] = mapped_column()
    campus: Mapped[str] = mapped_column(String(50))
    subject_rank: Mapped[str] = mapped_column(String(10))
    core_courses: Mapped[list] = mapped_column(JSON, default=list)
    required_math: Mapped[bool] = mapped_column(default=False)
    required_math_level: Mapped[str] = mapped_column(String(200), default="")
    semesters_needed: Mapped[int] = mapped_column(default=4)
    discipline: Mapped[str] = mapped_column(String(50))
    department: Mapped[str] = mapped_column(String(100), default="")  # 所属院系，对应 Course.department


class ProgramEnrollment(Base):
    """账号加入辅修方向的关系，用于统计真实参与人数。"""

    __tablename__ = "program_enrollments"
    __table_args__ = (
        UniqueConstraint("user_id", "program_name", name="uq_program_enrollments_user_program"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    program_name: Mapped[str] = mapped_column(ForeignKey("programs.name", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/left
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ProgramPlanItem(Base):
    __tablename__ = "program_plan_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_name: Mapped[str] = mapped_column(ForeignKey("programs.name", ondelete="CASCADE"))
    semester: Mapped[int] = mapped_column()
    term: Mapped[str] = mapped_column(String(20))
    course: Mapped[str] = mapped_column(String(200))
    credits: Mapped[int] = mapped_column()
    campus: Mapped[str] = mapped_column(String(50))


class Course(Base):
    """选课系统实际开设的课程（按教学班，同一课程可能有多个班）。"""
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    teaching_class_id: Mapped[str] = mapped_column(String(64), unique=True)  # 教学班ID（去重键）
    course_number: Mapped[str] = mapped_column(String(50), default="")
    course_name: Mapped[str] = mapped_column(String(200))
    teacher: Mapped[str] = mapped_column(String(500), default="")
    credit: Mapped[float] = mapped_column(Float)
    hours: Mapped[int] = mapped_column(default=0)
    teaching_class_type: Mapped[str] = mapped_column(String(20), default="")  # KZY=跨专业 / GG02=公选
    campus: Mapped[str] = mapped_column(String(50), default="")
    department: Mapped[str] = mapped_column(String(200), default="")
    teaching_place: Mapped[str] = mapped_column(Text, default="")
    school_term: Mapped[str] = mapped_column(String(20), default="")
    schedule: Mapped[list] = mapped_column(JSON, default=list)
    capacity: Mapped[int] = mapped_column(default=0)  # 0 表示暂未提供容量
    enrolled_count: Mapped[int] = mapped_column(default=0)
    source: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    employer: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(200))
    location: Mapped[str] = mapped_column(String(200))
    majors: Mapped[list] = mapped_column(JSON, default=list)
    preferred_cross: Mapped[list] = mapped_column(JSON, default=list)
    skills_required: Mapped[list] = mapped_column(JSON, default=list)
    skills_preferred: Mapped[list] = mapped_column(JSON, default=list)
    deadline: Mapped[str] = mapped_column(String(20))
    source: Mapped[str] = mapped_column(String(100))
    remote_type: Mapped[str] = mapped_column(String(50), default="")
    job_type: Mapped[str] = mapped_column(String(50), default="")
    arrival_time: Mapped[str] = mapped_column(String(100), default="")
    internship_duration: Mapped[str] = mapped_column(String(100), default="")
    responsibilities: Mapped[list] = mapped_column(JSON, default=list)
    application_email: Mapped[str] = mapped_column(String(200), default="")
    application_note: Mapped[str] = mapped_column(Text, default="")


class JobFavorite(Base):
    """账号级岗位收藏，替代浏览器本地存储。"""

    __tablename__ = "job_favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_job_favorites_user_job"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class JobApplication(Base):
    """账号级岗位跟进记录，不代替外部招聘网站的实际投递。"""

    __tablename__ = "job_applications"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_job_applications_user_job"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="interested")
    channel: Mapped[str] = mapped_column(String(100), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class UserContact(Base):
    """账号联系方式及其验证状态。"""

    __tablename__ = "user_contacts"
    __table_args__ = (
        UniqueConstraint("user_id", "contact_type", "value", name="uq_user_contacts_value"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    contact_type: Mapped[str] = mapped_column(String(20))  # phone / email
    value: Mapped[str] = mapped_column(String(200))
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class VerificationChallenge(Base):
    """联系方式验证码挑战；只保存摘要，不保存明文验证码。"""

    __tablename__ = "verification_challenges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    contact_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user_contacts.id", ondelete="CASCADE"))
    code_hash: Mapped[str] = mapped_column(String(128))
    code_salt: Mapped[str] = mapped_column(String(32))
    purpose: Mapped[str] = mapped_column(String(30), default="contact_verification")
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=5)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(20), default="queued")  # queued/sent/failed
    delivery_attempts: Mapped[int] = mapped_column(default=0)
    delivery_error: Mapped[str] = mapped_column(Text, default="")
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LearningRecord(Base):
    """账号级课程修读记录，用于学习进度汇总。"""

    __tablename__ = "learning_records"
    __table_args__ = (
        UniqueConstraint("user_id", "course_name", "term", name="uq_learning_records_course_term"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    course_name: Mapped[str] = mapped_column(String(200))
    course_code: Mapped[str] = mapped_column(String(50), default="")
    term: Mapped[str] = mapped_column(String(30))
    credits: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="completed")  # completed/in_progress/planned
    grade: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="manual")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class LearningActivity(Base):
    """账号级学习活动，用于统计学习天数和连续学习天数。"""

    __tablename__ = "learning_activities"
    __table_args__ = (
        UniqueConstraint("user_id", "activity_date", name="uq_learning_activities_user_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    activity_date: Mapped[date] = mapped_column()
    minutes: Mapped[int] = mapped_column(default=0)
    source: Mapped[str] = mapped_column(String(50), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class KnowledgeProgress(Base):
    """账号级知识点完成状态。"""

    __tablename__ = "knowledge_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "node_id", name="uq_knowledge_progress_user_node"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    node_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="todo")  # todo/progress/done/mastered
    progress_percent: Mapped[int] = mapped_column(default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
