import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, String, Text, DateTime, Float, JSON, ForeignKey, UniqueConstraint
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


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    feedback_type: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    contact: Mapped[str] = mapped_column(String(200), default="")
    attachments: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


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
