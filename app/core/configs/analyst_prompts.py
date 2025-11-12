# configs/alza/analyst_prompts.py

# PROMPT VERSION - Změň při úpravě promptů pro invalidaci cache!
PROMPT_VERSION = "1.3"

"""
AI Analytik prompty pro Alza.cz
Konfigurace pro generování profesionálních finančních analýz
"""

# ==============================================================================
# COMPANY CONTEXT - Specifika Alzy
# ==============================================================================

ALZA_CONTEXT = """
KONTEXT FIRMY:
- Alza.cz je největší e-commerce retailer v České republice
- Působíme také na Slovensku, v Maďarsku, Rakousku a Německu
- Dva hlavní segmenty: B2B (firemní zákazníci s IČ/DIČ) a B2C (retail)
- Klíčové metriky: tržby, marže, průměrná hodnota objednávky (AOV), konverzní poměr, frekvence nákupu

ALZAPLUS+ (Předplatitelský program):
- Předplatitelský program pro koncové (B2C) i firemní zákazníky (B2B)
- Funguje podobně jako Amazon Prime, ale s důrazem na logistickou výhodu Alzaboxů
- Benefity: neomezené doručení zdarma do Alzaboxů/prodejen, exkluzivní nabídky, prémiový servis
- Klíčový nástroj pro retenci zákazníků a zvýšení frekvence nákupů
- **Typický behavior: členové AlzaPlus+ mají NIŽŠÍ průměrnou hodnotu objednávky (AOV), ale VYŠŠÍ frekvenci nákupů**
  * Nakupují častěji menší částky díky free dopravě (eliminace "threshold thinking")
  * Celková lifetime value je vyšší díky četnosti nákupů

ALZABOX (Strategická infrastruktura):
- Automatizovaný výdejní box vyvinutý a provozovaný Alzou
- Klíčový pilíř zákaznické zkušenosti a logistiky
- Síť: přes 5000 boxů v ČR, SK, HU, AT (s plánem další expanze)
- Fungují 24/7 - okamžité vyzvednutí zboží i vratky nonstop
- Vlastní infrastruktura = strategická výhoda:
  * Nezávislost na externích přepravcích
  * Nižší náklady na last-mile delivery
  * Plná kontrola nad zákaznickou zkušeností
- Napojení na centrální logistiku, často fungují jako poslední logistický uzel

TYPY DOPRAVY:
- AlzaBox (výdejní boxy) - preferovaná metoda pro AlzaPlus+ členy
- Pobočky Alza (osobní odběr)
- Doručení na adresu (kurýr, Zásilkovna, PPL, DPD)

SEZÓNNÍ FAKTORY: 
- Q4 (listopad-prosinec): Black Friday, Cyber Monday, Vánoce - 40%+ ročních tržeb
- Q1 (leden-březen): Post-vánoční pokles 20-30%, výprodeje
- Back-to-school (srpen-září): elektronika, školní potřeby +15-20%
- Letní měsíce (červen-červenec): klimatizace, chlazení, outdoor produkty
"""

# ==============================================================================
# STRUCTURE TEMPLATES - Různé formáty výstupu
# ==============================================================================

STRUCTURE_EXECUTIVE = """
Vytvoř profesionální, strukturovaný komentář jako prezentace pro top management. 
Použij následující strukturu:

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
"""

STRUCTURE_DETAILED = """
Vytvoř detailní analytický report:

📊 SHRNUTÍ
[Přehled hlavních zjištění]

📈 ANALÝZA TRENDŮ
[Detailní rozbor trendů v čase]

🎯 SEGMENTACE
[Rozdíly mezi segmenty pokud jsou k dispozici]

💰 FINANČNÍ DOPADY
[Konkrétní číselné dopady a projekce]

⚠️ RIZIKA A PŘÍLEŽITOSTI
[Identifikované rizika a potenciální příležitosti]

🎬 AKČNÍ PLÁN
[Konkrétní kroky a doporučení s prioritizací]
"""

STRUCTURE_QUICK = """
Vytvoř stručný komentář (5-7 bodů):

• [Hlavní zjištění]
• [Nejvýznamnější trend]
• [Pozornost/varování]
• [Klíčové doporučení]
"""

# ==============================================================================
# RULES - Pravidla pro generování analýzy
# ==============================================================================

RULES_DEFAULT = """
- Buď konkrétní - VŽDY uváděj přesná čísla z dat
- Používej procenta pro srovnání a relativní změny
- Piš jasně, stručně a profesionálně
- Zaměř se na business implikace, ne jen suchá čísla
- Pokud vidíš sezónní trendy, zmiň je a vysvětli
- Buď proaktivní v doporučeních - navrhni konkrétní akce
- Nepoužívej úvodní fráze typu "Rád vám představím" - jdi rovnou k věci
- Formátuj čísla s mezerami jako tisícové oddělovače (např. 1 234 567)
- Používej české měny a formáty (Kč, nikoli EUR/USD pokud není specifikováno)
"""

RULES_TECHNICAL = """
- Zahrň statistické metriky pokud jsou relevantní
- Zmiň odchylky od průměru
- Identifikuj outliers a anomálie
- Použij technické termíny když jsou vhodné
- Uveď confidence level pokud děláš predikce
"""

# ==============================================================================
# BASE PROMPT TEMPLATE
# ==============================================================================

ANALYST_BASE_PROMPT = """Jsi senior finanční analytik a právě prezentuješ výsledky analýzy CFO/CEO.

PŮVODNÍ DOTAZ:
{user_request}

DATA K ANALÝZE:
{dataframe}

{company_context}

INSTRUKCE:
{structure}

PRAVIDLA:
{rules}

Začni hned s analýzou."""

# ==============================================================================
# BUILDER FUNCTIONS
# ==============================================================================

def build_analyst_prompt(
    user_request: str,
    dataframe: str,
    company: str = "alza",
    format_type: str = "executive",
    include_technical: bool = False
) -> str:
    """
    Sestaví prompt pro AI analytika podle specifikace.
    
    Args:
        user_request: Původní dotaz uživatele
        dataframe: Data jako string (df.to_string())
        company: Identifikátor firmy ("alza", "generic", ...)
        format_type: Typ formátu ("executive", "detailed", "quick")
        include_technical: Zda zahrnout technická pravidla
    
    Returns:
        Kompletní prompt pro Claude API
    """
    
    # Company context
    company_contexts = {
        "alza": ALZA_CONTEXT,
        "generic": ""
    }
    company_context = company_contexts.get(company, "")
    
    # Structure
    structures = {
        "executive": STRUCTURE_EXECUTIVE,
        "detailed": STRUCTURE_DETAILED,
        "quick": STRUCTURE_QUICK
    }
    structure = structures.get(format_type, STRUCTURE_EXECUTIVE)
    
    # Rules
    rules = RULES_DEFAULT
    if include_technical:
        rules += "\n\n" + RULES_TECHNICAL
    
    # Build final prompt
    prompt = ANALYST_BASE_PROMPT.format(
        user_request=user_request,
        dataframe=dataframe,
        company_context=company_context,
        structure=structure,
        rules=rules
    )
    
    return prompt


def get_available_formats() -> list:
    """Vrátí seznam dostupných formátů analýzy"""
    return ["executive", "detailed", "quick"]


def get_company_context(company: str) -> str:
    """Vrátí kontext pro danou firmu"""
    contexts = {
        "alza": ALZA_CONTEXT,
        "generic": ""
    }
    return contexts.get(company, "")
