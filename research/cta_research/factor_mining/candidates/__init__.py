"""因子研究:候选因子定义(catalog)、统一标准化(base)、新数据因子(newdata)、多源合成因子 MSF(composite);快速评估与多重检验在 factor_mining.evaluation.evaluate。
预注册见 docs/design_log.md 第四节;这里的代码不参与生产出单,生产信号在 cta.factor_library。"""

from cta_research.factor_mining.candidates.base import (
    REGISTRY,
    FactorInputs,
    FactorSpec,
    register,
    standardize,
)
from cta_research.factor_mining.candidates.catalog import ALL_FACTORS

__all__ = ["ALL_FACTORS", "REGISTRY", "FactorInputs", "FactorSpec", "register", "standardize"]
