"""
Wilco SaaS - Prompt Builder Service
Sestavuje prompty pro Claude AI podle business konfigurace
"""

from typing import Dict, List, Any


# ==============================================================================
# ALZA BUSINESS CONTEXT - Import z desktop aplikace
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

ALZABOX (Strategická infrastruktura):
- Automatizovaný výdejní box vyvinutý a provozovaný Alzou
- Klíčový pilíř zákaznické zkušenosti a logistiky
- Síť: přes 5000 boxů v ČR, SK, HU, AT
- Fungují 24/7 - okamžité vyzvednutí zboží i vratky nonstop

TYPY DOPRAVY:
- AlzaBox (výdejní boxy) - preferovaná metoda pro AlzaPlus+ členy
- Pobočky Alza (osobní odběr)
- Doručení na adresu (kurýr, Zásilkovna, PPL, DPD)

SEZÓNNÍ FAKTORY: 
- Q4 (listopad-prosinec): Black Friday, Cyber Monday, Vánoce - 40%+ ročních tržeb
- Q1 (leden-březen): Post-vánoční pokles 20-30%, výprodeje
- Back-to-school (srpen-září): elektronika, školní potřeby +15-20%
"""


# ==============================================================================
# DATA STRUCTURE INFO
# ==============================================================================

DATA_STRUCTURE_INFO = {
    "Sales.csv": {
        "format": "WIDE (pivoted)",
        "description": "Data jsou v WIDE formátu - datumy jsou sloupce (01.01.2024, 01.02.2024, ...)",
        "transformation": "MUSÍ být unpivoted (melt) na LONG formát",
        "date_columns": "Všechny sloupce ve formátu DD.MM.YYYY",
        "value_meaning": "Tržby v Kč bez DPH"
    },
    "Documents.csv": {
        "format": "LONG",
        "description": "Klasický long formát - každý řádek = jedna transakce"
    },
    "M3.csv": {
        "format": "MIXED",
        "description": "Kombinace dimenzí a časových sloupců"
    }
}


# ==============================================================================
# BUSINESS RULES - Alza Specific
# ==============================================================================

ALZA_BUSINESS_RULES = """
## CRITICAL BUSINESS RULES - ALZA:

### 1. B2B vs B2C Identifikace:
**EXACT STRING MATCHING ONLY!**
- B2B: "Customer is business customer (IN/TIN)" ← PŘESNĚ TENTO TEXT!
- B2C: "Customer is not business customer (IN/TIN)" ← PŘESNĚ TENTO TEXT!

```python
# ✅ SPRÁVNĚ:
b2b = df[df['Customer is business customer (IN/TIN)'] == 'Customer is business customer (IN/TIN)']
b2c = df[df['Customer is business customer (IN/TIN)'] == 'Customer is not business customer (IN/TIN)']

# ❌ ŠPATNĚ - NIKDY nepoužívat:
b2b = df[df['CustomerType'] == 'B2B']  # ← Tento sloupec neexistuje!
```

### 2. AlzaPlus+ Členství:
**EXACT STRING MATCHING ONLY!**
- Členové: "AlzaPlus+"
- Ne-členové: "Customer is not member of AlzaPlus+ program"

```python
# ✅ SPRÁVNĚ:
members = df[df['AlzaPlus+'] == 'AlzaPlus+']
non_members = df[df['AlzaPlus+'] == 'Customer is not member of AlzaPlus+ program']
```

### 3. Shipping Methods - KRITICKÉ PRAVIDLO:
**VŽDY používej 'ShippingType' z Bridge tabulky pro groupování!**

```python
# ✅ SPRÁVNĚ - Group by ShippingType:
merged = Sales.merge(Bridge, on='Shipping name', how='left')
grouped = merged.groupby('ShippingType')['Tržby'].sum()

# ❌ ŠPATNĚ - NIKDY negroupuj přímo podle 'Shipping name':
grouped = Sales.groupby('Shipping name')['Tržby'].sum()  # ← ŠPATNĚ!
```

**Důvod:** 'Shipping name' a 'Shipping detail name' jsou POUZE pro popis/labels!
Bridge tabulka mapuje detailní názvy → agregované typy (AlzaBox, Pobočky, Adresa)

### 4. Sales.csv - WIDE Format Handling:
**VŽDY jako první krok provést UNPIVOT (melt)!**

```python
# ✅ SPRÁVNĚ - UNPIVOT na začátku:
sales = Sales.copy()

# Najdi date columns
date_cols = [col for col in sales.columns 
             if '.' in col and any(char.isdigit() for char in col)]

# Ostatní sloupce = dimensions
id_cols = [col for col in sales.columns if col not in date_cols]

# MELT (unpivot)
sales_long = sales.melt(
    id_vars=id_cols,
    value_vars=date_cols,
    var_name='Datum',
    value_name='Tržby'
)

# Convert datatypes
sales_long['Tržby'] = pd.to_numeric(sales_long['Tržby'], errors='coerce')
sales_long['Datum'] = pd.to_datetime(sales_long['Datum'], format='%d.%m.%Y', errors='coerce')

# TEĎ můžeš filtrovat a groupovat!
```

### 5. Date Filtering:
```python
# ✅ Po UNPIVOT:
jan_2024 = sales_long[
    (sales_long['Datum'].dt.year == 2024) &
    (sales_long['Datum'].dt.month == 1)
]

# Pro rok 2024:
year_2024 = sales_long[sales_long['Datum'].dt.year == 2024]

# Pro Q1:
q1 = sales_long[
    (sales_long['Datum'].dt.year == 2024) &
    (sales_long['Datum'].dt.month.isin([1, 2, 3]))
]
```

### 6. Encoding:
**UTF-8 REQUIRED pro české znaky!**
```python
df = pd.read_csv('Sales.csv', encoding='utf-8', sep=';', decimal=',')
```

### 7. Output Formatting:
- České názvy sloupců
- Čísla s mezerami jako tisícové oddělovače: 1 234 567
- Procenta zaokrouhlená na 1 des. místo: 45.6%
- Řazení SESTUPNĚ (nejvyšší hodnoty první) pokud není řečeno jinak
"""


# ==============================================================================
# PROMPT BUILDER
# ==============================================================================

def build_business_prompt(
    user_query: str,
    available_datasets: List[str],
    user_context: Dict[str, Any] = None
) -> str:
    """
    Sestaví prompt pro generování Python kódu z business dotazu.
    
    Args:
        user_query: Dotaz uživatele v češtině
        available_datasets: Seznam dostupných CSV souborů
        user_context: Optional - kontext uživatele (firma, module, ...)
    
    Returns:
        Kompletní prompt pro Claude API
    """
    
    # Detekce dostupných datasetů
    datasets_info = []
    for dataset_name in available_datasets:
        if dataset_name in DATA_STRUCTURE_INFO:
            info = DATA_STRUCTURE_INFO[dataset_name]
            datasets_info.append(
                f"- {dataset_name}: {info['description']}"
            )
    
    datasets_section = "\n".join(datasets_info) if datasets_info else "Žádné datasety k dispozici."
    
    # Sestavení finálního promptu
    prompt = f"""Jsi expert Python data analytik pro Alza.cz. Generuješ Python kód pro analýzu dat.

{ALZA_CONTEXT}

## DOSTUPNÉ DATASETY:
{datasets_section}

{ALZA_BUSINESS_RULES}

## UŽIVATELSKÝ DOTAZ:
{user_query}

## INSTRUKCE PRO ODPOVĚĎ:

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
5. Pro Sales.csv VŽDY začni UNPIVOT operací
6. VŽDY řaď sestupně (highest first) pokud uživatel neřekne jinak
7. Pro měsíční data VŽDY zahrň YoY % a MoM % pokud jsou data k dispozici

**Dostupné knihovny:**
- pandas as pd
- numpy as np
- datetime

**Dostupné DataFrames v paměti:**
{', '.join([d.replace('.csv', '').replace('.xlsx', '').replace(' ', '_').replace('-', '_') for d in available_datasets])}

**CRITICAL: NIKDY nepoužívej pd.read_csv() nebo pd.read_excel()!**
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


def detect_module_type(datasets: List[str]) -> str:
    """
    Detekuje typ modulu podle dostupných datasetů.
    """
    if "PL.csv" in datasets or "OVH.csv" in datasets:
        return "accounting"
    elif "Sales.csv" in datasets:
        return "business"
    else:
        return "generic"
