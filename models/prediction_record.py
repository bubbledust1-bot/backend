"""
预测记录表：每次调用 /api/predict 落库一行，成功或失败均保存，便于复盘与答辩。

字段与 algorithm 返回契约对齐；不在此做任何业务校验。
"""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, Text, func

from database.session import Base


class PredictionRecord(Base):
    """
    prediction_records 表 ORM。

    JSON 列使用 SQLAlchemy JSON 类型；在 SQLite 中底层以文本存储，
    写入/读出时为 Python dict/list，无需手动 json.dumps（除非自定义类型）。
    """

    __tablename__ = "prediction_records"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="自增主键")

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="服务端记录创建时间（UTC）",
    )

    # 前端/客户端提交的原始 JSON（字典），完整留痕
    raw_input_json = Column(JSON, nullable=False, comment="原始请求体 JSON")

    # algorithm 成功时通常有值；失败时多为 null
    normalized_input_json = Column(JSON, nullable=True, comment="algorithm.normalized_input")
    input_for_model_json = Column(JSON, nullable=True, comment="algorithm.input_for_model 列表")

    prediction_mpa = Column(Float, nullable=True, comment="预测强度 MPa，失败为 null")

    success = Column(Boolean, nullable=False, comment="是否与 algorithm success 一致")

    # 存 warnings 列表（与 algorithm 的 warnings / warning 一致即可）
    warning_json = Column(JSON, nullable=True, comment="algorithm.warnings 列表")

    error_message = Column(Text, nullable=True, comment="algorithm.error 中文说明")

    model_version = Column(Text, nullable=True, comment="algorithm.model_version")

    # 答辩与复盘：完整保存 explain 对象
    explain_json = Column(JSON, nullable=True, comment="algorithm.explain")
