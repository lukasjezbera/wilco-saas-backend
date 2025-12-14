"""
Wilco SaaS - Prompt Builder Service
Sestavuje prompty pro Claude AI podle business konfigurace
ADAPTED FROM DESKTOP APPLICATION - Full feature parity
"""

from typing import Dict, List, Any


# ==============================================================================
# ALZA BUSINESS CONTEXT
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
# ACCOUNTING MODULE PROMPTS
# ==============================================================================

ACCOUNTING_MODULE_PROMPT = """
## ⚠️ CRITICAL: ACCOUNTING MODULE - RULES

### 1. DATASET SELECTION (CRITICAL!):

**⚠️ CRITICAL WARNING - READ THIS FIRST:**
- "Faktury" = EXPENSE INVOICES → Use OVH.csv (NOT Sales.csv!)
- Sales.csv is ONLY for REVENUE queries (tržby, prodej, customers)
- OVH.csv is for EXPENSE invoice details (dodavatelé, faktury, náklady)
- If user says "faktury" in cost context → MUST use OVH.csv!

**PL.csv** = Complete P&L statement (ALL costs and revenues aggregated)
- Has 'Account class' column (5 = costs, 6 = revenue)
- Has Cost Center columns: 'CC-Level 1', 'CC-Level 2'
- Has Cost Category columns: 'Acc-Level 1', 'Acc-Level 2', 'Acc-Level 3'
- Has Analytical account column
- Does NOT have: Vendor, ELD, Document description
- **WIDE FORMAT** with monthly columns: '01.01.2024', '01.02.2024', etc.

**USE PL.csv FOR:**
- "celkové náklady" / "total costs"
- "náklady střediska X" / "cost center X costs"
- "náklady kategorie Y" / "category Y costs"
- "účet 501 200" / "account queries"
- ANY query WITHOUT vendor/ELD/document description!

**OVH.csv** = Overhead details (EXPENSE INVOICES with vendor breakdown)
- **WIDE FORMAT** with monthly columns: '01.01.2024', '01.02.2024', etc.
- Each row = one invoice line item with amounts in monthly columns
- Has 'Customer/company name' column (vendor/supplier)
- Has 'Electronic document key' column (ELD = invoice number)
- Has 'Document item description' column

**USE OVH.csv ONLY FOR:**
- "faktury" / "invoices" (in COST context!)
- "dodavatel X" / "vendor X"
- "ELD číslo" / "invoice number"
- "faktury obsahující..." / "invoice description"

### 2. WIDE FORMAT HANDLING (PL & OVH):

Both PL.csv and OVH.csv use WIDE FORMAT with MONTHLY columns:
- '01.01.2024' = CELÝ LEDEN 2024
- '01.02.2024' = CELÝ ÚNOR 2024
- Each column = one full month

**TWO STRATEGIES:**

**STRATEGY A - STAY WIDE (for simple queries):**
```python
# Example: "Náklady střediska Finance v lednu 2024"
pl = PL.copy()
pl_costs = pl[pl['Account class'] == 5].copy()  # Filter costs

finance = pl_costs[
    pl_costs['CC-Level 1'].str.contains('FINANCE', case=False, na=False)
].copy()

jan_col = '01.01.2024'
finance[jan_col] = pd.to_numeric(finance[jan_col], errors='coerce').fillna(0)
total_jan = finance[jan_col].sum()
```

**STRATEGY B - UNPIVOT (for trends/time-series):**
Only use when user wants trends, YoY, MoM, or multi-month analysis.

### 3. ACCOUNT CLASS FILTERING (MANDATORY for PL.csv):

**Account class values:**
- "5" = Náklady (Costs) ← PRIMARY USE
- "6" = Výnosy (Revenue) ← Only for specific account queries

**ALWAYS filter Account class = 5 unless user asks for revenue accounts!**

### 4. NUMERIC DATA CLEANING:

```python
# Convert monthly columns to numeric
for col in monthly_cols:
    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
```

### 5. EXAMPLES:

```python
# ✅ Cost center query (WIDE):
pl_costs = PL[PL['Account class'] == 5].copy()
finance = pl_costs[pl_costs['CC-Level 1'] == 'FINANCE']
jan_total = finance['01.01.2024'].sum()

# ✅ Vendor query (WIDE):
ovh = OVH.copy()
vendor_data = ovh[ovh['Customer/company name'].str.contains('KPK', case=False, na=False)]
jan_total = vendor_data['01.01.2024'].sum()

# ✅ ELD query:
ovh = OVH.copy()
invoice = ovh[ovh['Electronic document key'] == 'ELD5724723']
```
"""


# ==============================================================================
# BUSINESS MODULE PROMPTS  
# ==============================================================================

BUSINESS_MODULE_PROMPT = """
## CRITICAL BUSINESS RULES - ALZA:

### 1. B2B vs B2C Identifikace:
**EXACT STRING MATCHING ONLY!**
- B2B: "Customer is business customer (IN/TIN)"
- B2C: "Customer is not business customer (IN/TIN)"

```python
# ✅ SPRÁVNĚ:
b2b = df[df['Customer is business customer (IN/TIN)'] == 'Customer is business customer (IN/TIN)']
b2c = df[df['Customer is business customer (IN/TIN)'] == 'Customer is not business customer (IN/TIN)']
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

### 3. Geographic Analysis (Země/Country):
**CRITICAL: Column name is 'Eshop site country' (NOT 'Country' or 'Země')!**

When user asks about "země", "zemí", "country", "trh", "market":
```python
# ✅ SPRÁVNĚ - Use 'Eshop site country':
country_revenue = sales.groupby('Eshop site country')[month_col].sum()

# ❌ ŠPATNĚ:
country_revenue = sales.groupby('Country')[month_col].sum()  # ← Column doesn't exist!
country_revenue = sales.groupby('Země')[month_col].sum()     # ← Column doesn't exist!
```

**Possible values:**
- 'Česká republika' (primary market, 70-80% revenue)
- 'Slovensko' (key expansion market)
- 'Maďarsko' (key expansion market)
- 'Rakousko' (new market)
- 'Německo' (new market)

**CRITICAL: Country Code Mapping**
Users may use shortcuts/codes - ALWAYS map to full Czech names:

```python
# Define country mapping dictionary
COUNTRY_MAP = {
    # Czech Republic variants
    'CZ': 'Česká republika',
    'CR': 'Česká republika',
    'Česko': 'Česká republika',
    'Čechy': 'Česká republika',
    'Czech Republic': 'Česká republika',
    'Czech': 'Česká republika',
    
    # Slovakia variants
    'SK': 'Slovensko',
    'Slovakia': 'Slovensko',
    
    # Hungary variants
    'HU': 'Maďarsko',
    'Hungary': 'Maďarsko',
    'Madarsko': 'Maďarsko',  # common typo
    
    # Austria variants
    'AT': 'Rakousko',
    'Austria': 'Rakousko',
    
    # Germany variants
    'DE': 'Německo',
    'Germany': 'Německo',
    'Nemecko': 'Německo'  # common typo
}

# Example 1: Query "Tržby v CZ a SK"
user_countries = ['CZ', 'SK']
full_names = [COUNTRY_MAP.get(c.upper(), c) for c in user_countries]
# Result: ['Česká republika', 'Slovensko']

filtered = sales[sales['Eshop site country'].isin(full_names)]

# Example 2: Query "Tržby v Čechách"
user_input = 'Čechy'
full_name = COUNTRY_MAP.get(user_input, user_input)
# Result: 'Česká republika'

cz_sales = sales[sales['Eshop site country'] == full_name]

# Example 3: Query "Porovnej CZ vs SK vs HU"
codes = ['CZ', 'SK', 'HU']
countries = [COUNTRY_MAP.get(c, c) for c in codes]
comparison = sales[sales['Eshop site country'].isin(countries)].groupby('Eshop site country')[month_col].sum()
```

### 4. Shipping Methods - KRITICKÉ PRAVIDLO:
**VŽDY používej 'ShippingType' z Bridge tabulky pro groupování!**

```python
# ✅ SPRÁVNĚ - Group by ShippingType:
merged = Sales.merge(Bridge, on='Shipping name', how='left')
grouped = merged.groupby('ShippingType')['Tržby'].sum()

# ❌ ŠPATNĚ:
grouped = Sales.groupby('Shipping name')['Tržby'].sum()  # ← NIKDY!
```

### 5. Sales.csv - WIDE FORMAT HANDLING:

**CRITICAL UNDERSTANDING:**
- Sales.csv má sloupce: 01.01.2024, 01.02.2024, 01.03.2024, ...
- **Každý sloupec = CELÝ MĚSÍC!** (01.01.2024 = CELÝ LEDEN 2024)
- Dimenze (řádky): AlzaPlus+, Payment detail name, Customer is business customer (IN/TIN), Shipping name, atd.

**TWO STRATEGIES:**

### **STRATEGY A: STAY WIDE (for simple queries)**
Use when user asks about ONE MONTH or YEAR:

```python
# ✅ Example: "Tržby v únoru 2024"
sales = Sales.copy()
feb_col = '01.02.2024'
total_feb = sales[feb_col].sum()

result = pd.DataFrame({
    'Měsíc': ['Únor 2024'],
    'Tržby (Kč)': [f'{total_feb:,.0f}'.replace(',', ' ')]
})
```

```python
# ✅ Example: "Platební metody v lednu 2024"
sales = Sales.copy()
jan_col = '01.01.2024'

payment_summary = sales.groupby('Payment detail name')[jan_col].sum().reset_index()
payment_summary.columns = ['Platební metoda', 'Tržby (Kč)']
payment_summary['Tržby (Kč)'] = payment_summary['Tržby (Kč)'].apply(
    lambda x: f'{x:,.0f}'.replace(',', ' ')
)
payment_summary = payment_summary.sort_values('Tržby (Kč)', ascending=False)

result = payment_summary
```

```python
# ✅ Example: "Breakdown tržeb podle zemí v lednu 2024"
sales = Sales.copy()
jan_col = '01.01.2024'

# CRITICAL: Use 'Eshop site country' (NOT 'Country'!)
country_revenue = sales.groupby('Eshop site country')[jan_col].sum().reset_index()
country_revenue.columns = ['Země', 'Tržby']

# Calculate percentages
total = country_revenue['Tržby'].sum()
country_revenue['Podíl %'] = (country_revenue['Tržby'] / total * 100)

# Format
country_revenue['Tržby (Kč)'] = country_revenue['Tržby'].apply(
    lambda x: f'{x:,.0f}'.replace(',', ' ')
)
country_revenue['Podíl %'] = country_revenue['Podíl %'].apply(lambda x: f'{x:.1f}%')

# Sort descending
country_revenue = country_revenue.sort_values('Tržby', ascending=False)

result = country_revenue[['Země', 'Tržby (Kč)', 'Podíl %']]
```

```python
# ✅ Example: "B2B vs B2C v roce 2024"
sales = Sales.copy()

# Find all 2024 columns
cols_2024 = [col for col in sales.columns if '2024' in col and '.' in col]

# Group by B2B/B2C and sum across all months
b2b_summary = sales.groupby('Customer is business customer (IN/TIN)')[cols_2024].sum().sum(axis=1).reset_index()
b2b_summary.columns = ['Segment', 'Tržby 2024 (Kč)']
b2b_summary['Tržby 2024 (Kč)'] = b2b_summary['Tržby 2024 (Kč)'].apply(
    lambda x: f'{x:,.0f}'.replace(',', ' ')
)

result = b2b_summary
```

### **STRATEGY B: UNPIVOT (for time-series)**
Use ONLY when user wants:
- Time-series (trend over months)
- YoY/MoM comparisons
- Monthly breakdown
- Charts over time

```python
# ✅ Example: "Měsíční vývoj tržeb v roce 2024"
sales = Sales.copy()

# Find date columns for 2024
date_cols = [col for col in sales.columns 
             if '.' in col and any(char.isdigit() for char in col)]
date_cols_2024 = [col for col in date_cols if '2024' in col]

# Melt
id_cols = [col for col in sales.columns if col not in date_cols]

sales_long = sales.melt(
    id_vars=id_cols,
    value_vars=date_cols_2024,
    var_name='Datum',
    value_name='Tržby'
)

# Convert datatypes
sales_long['Tržby'] = pd.to_numeric(sales_long['Tržby'], errors='coerce')
sales_long['Datum'] = pd.to_datetime(sales_long['Datum'], format='%d.%m.%Y', errors='coerce')

# Monthly aggregation
monthly = sales_long.groupby('Datum')['Tržby'].sum().reset_index()
monthly = monthly.sort_values('Datum')
monthly['Měsíc'] = monthly['Datum'].dt.strftime('%B %Y')

result = monthly[['Měsíc', 'Tržby']]
```

**DECISION TREE:**

```
Query contains "trend", "vývoj", "over time", "měsíční breakdown"?
  → YES → UNPIVOT (Strategy B)
  → NO  → STAY WIDE (Strategy A)

Query asks for more than 3 months?
  → YES → UNPIVOT (Strategy B)
  → NO  → STAY WIDE (Strategy A)

Query wants YoY or MoM comparison?
  → YES → UNPIVOT (Strategy B)
  → NO  → STAY WIDE (Strategy A)
```

### 6. Date Filtering & Column Selection:

**FOR WIDE FORMAT (Strategy A):**
```python
# One month:
feb_col = '01.02.2024'
total = sales[feb_col].sum()

# Year 2024:
cols_2024 = [col for col in sales.columns if '2024' in col and '.' in col]
total_2024 = sales[cols_2024].sum().sum()

# Q1 2024:
q1_cols = ['01.01.2024', '01.02.2024', '01.03.2024']
total_q1 = sales[q1_cols].sum().sum()
```

**FOR UNPIVOT (Strategy B):**
```python
# After unpivot:
jan_2024 = sales_long[
    (sales_long['Datum'].dt.year == 2024) &
    (sales_long['Datum'].dt.month == 1)
]
```

### 7. UTF-8 Encoding:
Not needed in SaaS - DataFrames are already loaded!

### 8. Output Formatting:
- České názvy sloupců
- Čísla s mezerami: `f'{value:,.0f}'.replace(',', ' ')`
- Procenta: `f'{pct:.1f}%'`
- Řazení SESTUPNĚ pokud není řečeno jinak
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
        user_context: Optional - kontext uživatele
    
    Returns:
        Kompletní prompt pro Claude API
    """
    
    # Detect module type
    module_type = detect_module_type(available_datasets)
    
    # Build datasets info
    datasets_info = []
    for dataset_name in available_datasets:
        datasets_info.append(f"- {dataset_name}")
    datasets_section = "\n".join(datasets_info) if datasets_info else "Žádné datasety k dispozici."
    
    # Select appropriate module prompts
    module_instructions = ""
    
    if module_type == "accounting":
        module_instructions = ACCOUNTING_MODULE_PROMPT
    elif module_type == "business":
        module_instructions = BUSINESS_MODULE_PROMPT
    elif module_type == "mixed":
        module_instructions = ACCOUNTING_MODULE_PROMPT + "\n\n" + BUSINESS_MODULE_PROMPT
    
    # Build final prompt
    prompt = f"""Jsi expert Python data analytik pro Alza.cz. Generuješ Python kód pro analýzu dat.

{ALZA_CONTEXT}

## DOSTUPNÉ DATASETY:
{datasets_section}

{module_instructions}

## UŽIVATELSKÝ DOTAZ:
{user_query}

## INSTRUKCE PRO ODPOVĚĎ:

**⚠️ CRITICAL: NEVER CREATE FAKE/SIMULATED DATA!**

You MUST use the actual DataFrames that are already loaded in memory:
- `Sales` - the Sales.csv data (already loaded as DataFrame)
- `Bridge_Shipping_Types` - the bridge table (already loaded as DataFrame)
- `PL` - the PL.csv data (if available)
- `OVH` - the OVH.csv data (if available)

**❌ NEVER DO THIS:**
```python
# ❌ Creating fake/simulated data
df = pd.DataFrame({
    'Země': ['Česká republika', 'Slovensko'],
    'Tržby': [450000000, 85000000]
})
```

**✅ ALWAYS DO THIS:**
```python
# ✅ Use actual loaded DataFrames
sales = Sales.copy()
country_revenue = sales.groupby('Eshop site country')[month_col].sum()
```

If you create simulated data, the query will return "undefined" values and fail!

---

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

**⚠️ CRITICAL: Column Formatting Order**

When calculating derived columns (MoM%, YoY%, changes, deltas):

**RULE: Calculate ALL numeric columns FIRST, then format at the END!**

❌ WRONG ORDER (will cause "undefined"):
```python
# ❌ Formatting before calculating derivatives
df['Podíl (%)'] = df['Podíl'].apply(lambda x: f'{x:.1f}%')  # Converts to string!
df['MoM změna'] = df['Podíl (%)'].diff()  # ERROR! Can't diff strings → undefined!
```

✅ CORRECT ORDER:
```python
# ✅ Step 1: Calculate ALL numeric columns first
df['MoM_change_numeric'] = df['Podíl'].diff()
df['YoY_change_numeric'] = df['Podíl'].pct_change(12) * 100

# ✅ Step 2: Format everything at the end
df['Podíl (%)'] = df['Podíl'].apply(lambda x: f'{x:.1f}%')
df['MoM změna (p.p.)'] = df['MoM_change_numeric'].apply(lambda x: f'{x:+.1f}p.p.' if pd.notna(x) else '-')
df['YoY změna (%)'] = df['YoY_change_numeric'].apply(lambda x: f'{x:+.1f}%' if pd.notna(x) else '-')

# ✅ Step 3: Select final columns (drop temp numeric columns)
result = df[['Měsíc', 'Podíl (%)', 'MoM změna (p.p.)', 'YoY změna (%)']]
```

**Why this matters:**
- Formatted strings (e.g., "32.8%") cannot be used in math operations
- `.diff()`, `.pct_change()`, subtraction, division require numeric values
- Always keep numeric versions until ALL calculations are done

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
