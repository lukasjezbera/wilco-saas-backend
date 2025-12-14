"""
Wilco SaaS - Modular Prompts Package
Obsahuje modulární prompt komponenty pro různé datasety
"""

from .base_prompt import CORE_INSTRUCTIONS
from .sales_prompt import ALZA_CONTEXT, SALES_ECOSYSTEM_INSTRUCTIONS
from .accounting_prompt import ACCOUNTING_ECOSYSTEM_INSTRUCTIONS

__all__ = [
    'CORE_INSTRUCTIONS',
    'ALZA_CONTEXT',
    'SALES_ECOSYSTEM_INSTRUCTIONS',
    'ACCOUNTING_ECOSYSTEM_INSTRUCTIONS'
]
