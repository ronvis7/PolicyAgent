"""政策匹配简报领域模型（主线尾巴：把已算出的情报组装成可导出交付物）。

简报不引入任何新数据源，纯组装已有能力的结果：
- ③ 匹配到的政策（来自工作台 Feed 的已物化条目，含推荐理由与申报截止快照）；
- ⑥ 资质差距分析（逐条达标/不达标/待确认，沿用风险纪律）；
- ⑤ 临期申报项（截止在窗口内的机会）。

风险纪律：差距/截止均承载结构性概要，`disclaimer` 必须随简报一并呈现，严禁当权威输出。
"""

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field

from app.domain.models.enterprise_profile import EnterpriseProfile
from app.domain.models.feed_item import FeedItem
from app.domain.models.qualification import QualificationGapReport

# 简报统一免责声明（与资质/截止口径一致）
REPORT_DISCLAIMER = (
    "本简报由系统依据企业档案与公开政策自动匹配生成，"
    "所列政策条件、资质门槛、申报截止均为结构性概要，"
    "具体以各官方主管部门当年最新办法与原文为准，不构成申报建议。"
)


class ReportData(BaseModel):
    """一份政策匹配简报的完整内容（组装层产物，供渲染器消费）。"""

    tenant_id: str = ""
    generated_at: datetime = Field(default_factory=datetime.now)
    profile: EnterpriseProfile  # 企业画像
    matched_policies: List[FeedItem] = Field(default_factory=list)  # ③ 匹配政策（按分排序）
    qualification_gaps: List[QualificationGapReport] = Field(default_factory=list)  # ⑥ 资质差距
    expiring: List[FeedItem] = Field(default_factory=list)  # ⑤ 临期申报项
    disclaimer: str = REPORT_DISCLAIMER
