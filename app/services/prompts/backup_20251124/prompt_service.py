"""
Wilco SaaS - Prompt Builder Service
Sestavuje prompty pro Claude AI podle business konfigurace
ADAPTED FROM DESKTOP APPLICATION - Full feature parity

✨ REFACTORED: Modular prompt architecture
- base_prompt.py: Core instructions (WIDE format, NO CELKEM, pandas)
- sales_prompt.py: Sales ecosystem (Sales + Documents + M3 + Bridge)
- accounting_prompt.py: P&L ecosystem (PL + OVH)
"""

from typing import Dict, List, Any

# Import modular prompts
try:
    from .prompts.base_prompt import CORE_INSTRUCTIONS
    from .prompts.sales_prompt import ALZA_CONTEXT, SALES_ECOSYSTEM_INSTRUCTIONS
    from .prompts.accounting_prompt import ACCOUNTING_ECOSYSTEM_INSTRUCTIONS
except ImportError:
    # Fallback if running standalone
    from app.services.prompts.base_prompt import CORE_INSTRUCTIONS
    from app.services.prompts.sales_prompt import ALZA_CONTEXT, SALES_ECOSYSTEM_INSTRUCTIONS
    from app.services.prompts.accounting_prompt import ACCOUNTING_ECOSYSTEM_INSTRUCTIONS


# ==============================================================================
# MODULE DETECTION
# ==============================================================================

def detect_module_type(available_datasets: List[str]) -> str:
    """
    Detekuje typ modulu podle dostupných datasetů.
    
    Returns:
        "accounting" | "business" | "mixed"
    """
    has_accounting = any(d in ['PL.csv', 'OVH.csv'] for d in available_datasets)
    has_business = any(d in ['Sales.csv', 'Documents.csv', 'M3.csv'] for d in available_datasets)
    
    if has_accounting and has_business:
        return "mixed"
    elif has_accounting:
        return "accounting"
    elif has_business:
        return "business"
    else:
        return "generic"


# ==============================================================================
# PROMPT BUILDER - MAIN FUNCTION
# ==============================================================================

def build_claude_prompt(
    user_query: str,
    available_datasets: List[str],
    context_query: str = None,
    context_code: str = None,
    query_chain: List[str] = None
) -> str:
    """
    Sestaví prompt pro Claude AI z modulárních komponent.
    
    Args:
        user_query: Dotaz uživatele
        available_datasets: Seznam dostupných datasetů
        context_query: Předchozí dotaz (pro follow-up)
        context_code: Předchozí kód (pro follow-up)
        query_chain: Historie dotazů (pro multi-level)
    
    Returns:
        Kompletní prompt pro Claude
    """
    
    # Detect module type
    module_type = detect_module_type(available_datasets)
    
    # ==============================================================================
    # BUILD PROMPT FROM MODULES
    # ==============================================================================
    
    prompt = ""
    
    # 1. CORE INSTRUCTIONS (always first!)
    prompt += CORE_INSTRUCTIONS
    prompt += "\n\n"
    
    # 2. ALZA CONTEXT (if Sales ecosystem)
    if module_type in ["business", "mixed"]:
        prompt += ALZA_CONTEXT
        prompt += "\n\n"
    
    # 3. DATASET-SPECIFIC INSTRUCTIONS
    
    if module_type == "business":
        # Sales ecosystem only
        prompt += SALES_ECOSYSTEM_INSTRUCTIONS
        
    elif module_type == "accounting":
        # Accounting ecosystem only
        prompt += ACCOUNTING_ECOSYSTEM_INSTRUCTIONS
        
    elif module_type == "mixed":
        # Both ecosystems
        prompt += "## ⚠️ MIXED ECOSYSTEMS AVAILABLE:\n\n"
        prompt += "You have access to BOTH Sales and Accounting datasets!\n\n"
        prompt += SALES_ECOSYSTEM_INSTRUCTIONS
        prompt += "\n\n"
        prompt += ACCOUNTING_ECOSYSTEM_INSTRUCTIONS
    
    prompt += "\n\n"
    
    # 4. AVAILABLE DATASETS SECTION
    datasets_section = "## DOSTUPNÉ DATASETY:\n\n"
    for dataset in available_datasets:
        datasets_section += f"- {dataset}\n"
    
    prompt += datasets_section
    prompt += "\n\n"
    
    # 5. CONTEXT (for follow-up queries)
    if context_query or context_code or query_chain:
        prompt += "## KONTEXT PŘEDCHOZÍCH DOTAZŮ:\n\n"
        
        if query_chain and len(query_chain) > 1:
            # Multi-level follow-up
            prompt += "**Query chain (complete history):**\n"
            for i, q in enumerate(query_chain, 1):
                prompt += f"{i}. {q}\n"
            prompt += "\n"
        
        if context_query:
            prompt += f"**Previous query:** {context_query}\n\n"
        
        if context_code:
            # Detect which dataset was used
            dataset_used = "Unknown"
            if 'PL.copy()' in context_code or 'pl = PL' in context_code.lower():
                dataset_used = "PL.csv (P&L expenses)"
            elif 'OVH.copy()' in context_code or 'ovh = OVH' in context_code.lower():
                dataset_used = "OVH.csv (detailed expense documents)"
            elif 'Sales.copy()' in context_code or 'sales = Sales' in context_code.lower():
                dataset_used = "Sales.csv (revenue)"
            elif 'M3.copy()' in context_code or 'm3 = M3' in context_code.lower():
                dataset_used = "M3.csv (margin)"
            elif 'Documents.copy()' in context_code or 'docs = Documents' in context_code.lower():
                dataset_used = "Documents.csv (order counts)"
            
            prompt += f"**→ Previous dataset: {dataset_used}**\n\n"
            prompt += "**⚠️⚠️⚠️ CRITICAL: CONTINUE USING THE SAME DATASET!**\n"
            prompt += "- If previous used PL.csv → CONTINUE with PL.csv!\n"
            prompt += "- If previous used OVH.csv → CONTINUE with OVH.csv!\n"
            prompt += "- DO NOT switch datasets unless user explicitly asks!\n\n"
            
            prompt += f"**Previous code (first 500 chars):**\n```python\n{context_code[:500]}\n```\n\n"
        
        prompt += "\n"
    
    # 6. USER QUERY
    prompt += f"## UŽIVATELSKÝ DOTAZ:\n{user_query}\n\n"
    
    # 7. OUTPUT INSTRUCTIONS
    prompt += """## INSTRUKCE PRO ODPOVĚĎ:

**CRITICAL: První řádek MUSÍ být title!**

**Formát odpovědi:**
```python
title = "Krátký popisný název"

# ... zbytek kódu ...

result = [tvůj_dataframe]
```

**Pravidla pro title:**
- MUSÍ být na prvním řádku ve formátu: title = "Název"
- Krátký (max 60 znaků), jasný, bez otázek
- Transformuj dotaz do názvu:
  * "Jaké byly tržby v lednu 2025?" → title = "Tržby leden 2025"
  * "Top 10 zákazníků" → title = "Top 10 zákazníků"
- Bez zbytečných slov ("Jaké", "Kolik", "Zobraz")
- Český jazyk

**Další pravidla:**
1. Vygeneruj POUZE Python kód bez dalšího textu (kromě title)
2. Kód musí být spustitelný bez úprav
3. Nepoužívej markdown code blocks (```)
4. Poslední řádek MUSÍ být: result = [tvůj_dataframe]
5. VŽDY řaď sestupně (highest first) pokud uživatel neřekne jinak
6. Pro měsíční data VŽDY zahrň YoY % a MoM % pokud jsou data k dispozici

**Dostupné knihovny:**
- pandas as pd
- numpy as np
- datetime

**Dostupné DataFrames v paměti:**
"""
    
    dataframe_names = ', '.join([
        d.replace('.csv', '').replace('.xlsx', '').replace(' ', '_').replace('-', '_') 
        for d in available_datasets
    ])
    prompt += dataframe_names
    prompt += "\n\n"
    
    prompt += """**CRITICAL: NIKDY nepoužívej pd.read_csv() nebo pd.read_excel()!**
DataFrames jsou UŽ NAČTENÉ v paměti. Použij je přímo:
```python
# ✅ SPRÁVNĚ - DataFrame už existuje:
sales = Sales.copy()

# ❌ ŠPATNĚ - NIKDY NEPOUŽÍVAT:
sales = pd.read_csv('Sales.csv', ...)  # ← NIKDY!
```

Začni generovat kód NYNÍ (nezapomeň na title na prvním řádku!):"""
    
    return prompt


def build_analyst_prompt(
    user_query: str,
    data_result: str,
    format_type: str = "executive"
) -> str:
    """
    Sestaví prompt pro AI Analytika (interpretaci výsledků).
    
    Args:
        user_query: Původní dotaz uživatele
        data_result: Data jako string (df.to_string())
        format_type: Typ formátu ("executive", "detailed", "quick")
    
    Returns:
        Prompt pro interpretaci výsledků
    """
    
    structures = {
        "executive": """
📊 EXECUTIVE SUMMARY
[1-2 věty - co data říkají na první pohled, hlavní závěr]

🔍 KLÍČOVÉ POZNATKY
• [Nejvyšší/nejnižší hodnoty s konkrétními čísly]
• [Trendy a změny - včetně MoM, YoY pokud jsou k dispozici]
• [Důležité milníky nebo zlomové body v datech]

⚠️ POZORNOST
[Oblasti vyžadující pozornost - poklesy, anomálie, potenciální rizika]

💡 DOPORUČENÍ
[2-3 konkrétní actionable doporučení pro management]
""",
        "quick": """
Vytvoř stručný komentář (5-7 bodů):
• [Hlavní zjištění]
• [Nejvýznamnější trend]
• [Pozornost/varování]
• [Klíčové doporučení]
"""
    }
    
    structure = structures.get(format_type, structures["executive"])
    
    prompt = f"""Jsi senior finanční analytik a právě prezentuješ výsledky analýzy CFO/CEO.

PŮVODNÍ DOTAZ:
{user_query}

DATA K ANALÝZE:
{data_result}

{ALZA_CONTEXT}

INSTRUKCE:
{structure}

PRAVIDLA:
- Buď konkrétní - VŽDY uváděj přesná čísla z dat
- Používej procenta pro srovnání a relativní změny
- Piš jasně, stručně a profesionálně
- Zaměř se na business implikace, ne jen suchá čísla
- Pokud vidíš sezónní trendy, zmiň je a vysvětli
- Buď proaktivní v doporučeních - navrhuj konkrétní akce
- Nepoužívej úvodní fráze typu "Rád vám představím" - jdi rovnou k věci
- Formátuj čísla s mezerami jako tisícové oddělovače (např. 1 234 567)
- Používej české měny a formáty (Kč)

Začni hned s analýzou."""
    
    return prompt


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def get_available_datasets_from_db(user_id: str) -> List[str]:
    """
    Načte seznam dostupných datasetů pro uživatele z databáze.
    TODO: Implementovat databázový dotaz
    """
    # Placeholder - bude nahrazeno DB query
    return ["Sales.csv", "Documents.csv", "M3.csv", "Bridge_Shipping_Types.csv"]

# Backward compatibility alias:
build_business_prompt = build_claude_prompt
