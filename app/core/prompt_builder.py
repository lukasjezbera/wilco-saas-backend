"""
Prompt builder pro generování Python kódu z uživatelských požadavků.
"""

def build_prompt(user_request: str, datasets_info: str, available_dataframes: list, module_config: dict) -> str:
    """
    Sestaví prompt pro Claude API s důrazem na správné datové typy a bezpečné operace.
    
    Args:
        user_request: Požadavek uživatele v přirozené řeči
        datasets_info: Informace o dostupných datasetech
        available_dataframes: Seznam názvů dostupných DataFrames
        module_config: Konfigurace business pravidel z business_config
    
    Returns:
        Kompletní prompt pro Claude API
    """
    
    # Extrahuj business pravidla z konfigurace
    business_rules = module_config.get('BUSINESS_RULES', {})
    data_structure_info = module_config.get('DATA_STRUCTURE_INFO', {})
    column_definitions = module_config.get('COLUMN_DEFINITIONS', {})
    alza_specific_rules = module_config.get('ALZA_SPECIFIC_RULES', {})
    
    # Detect module type
    required_files = module_config.get('REQUIRED_FILES', {})
    is_accounting = 'PL' in required_files or 'OVH' in required_files
    is_business = 'Sales' in required_files or 'Documents' in required_files
    
    # Module-specific date handling
    if is_accounting:
        module_name = "ACCOUNTING"
        date_handling_instructions = """
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

**USE PL.csv FOR:**
- "celkové náklady" / "total costs"
- "náklady střediska X" / "cost center X costs"
- "náklady kategorie Y" / "category Y costs"
- "účet 501 200" / "account queries"
- ANY query WITHOUT vendor/ELD/document description/faktury!

**OVH.csv** = Overhead details (EXPENSE INVOICES with vendor breakdown)

**⚠️ CRITICAL - OVH STRUCTURE:**
- **WIDE FORMAT** with monthly columns: '01.01.2024', '01.02.2024', etc.
- **NO 'Invoice date', 'Document date', or 'Amount' column!**
- Each row = one invoice line item with amounts in monthly columns
- To get total per invoice: sum across monthly columns!

**Columns:**
- Does NOT have 'Account class' column (all records are costs)
- Has Cost Center columns: 'CC-Level 1', 'CC-Level 2'
- Has Cost Category columns: 'Acc-Level 1', 'Acc-Level 2', 'Acc-Level 3'
- Has 'Customer/company name' column (vendor/supplier)
- Has 'Electronic document key' column (ELD number = invoice number)
- Has 'Document item description' column (what's on the invoice)
- **CRITICAL: WIDE FORMAT** - Monthly columns: '01.01.2024', '01.02.2024', etc.
- **NO 'Document date' or 'Amount' column!** Data is in monthly columns!

**OVH.csv STRUCTURE:**
```
ELD | Customer/company name | Description | CC-Level 1 | Acc-Level 1 | 01.01.2024 | 01.02.2024 | ...
```

**USE OVH.csv ONLY FOR:**
- **"faktury" / "invoices" (in COST context, NOT revenue!)**
- "dodavatel X" / "vendor X" / "kolik jsme zaplatili firmě X"
- "ELD číslo" / "faktura ELD123" / "invoice number"
- "faktury obsahující..." / "popis faktury" / "invoice description"
- "nákladová faktura" / "expense invoice"
- **ANY query explicitly asking for vendor/ELD/document description!**

**KEYWORDS FOR OVH:**
- Vendor: "dodavatel", "firma", "vendor", "kolik jsme zaplatili firmě", "společnosti", "company"
- ELD: "ELD", "faktura číslo", "Electronic document", "invoice number"
- Description: "popis faktury", "faktury obsahující", "description", "nákup"
- **CRITICAL: "faktura" / "invoice" when referring to COSTS/EXPENSES (not revenue!)**
- **CRITICAL: "faktury společnosti X" = expense invoices FROM vendor X (use OVH!)**

**DISTINGUISH: Faktury (invoices) - OVH vs Sales:**
- "Faktury obsahující 'samolepky'" → OVH.csv ✅ (expense invoices from vendors)
- "Faktury společnosti Direct Parcel" → OVH.csv ✅ (invoices FROM this vendor!)
- "Top 10 faktur společnosti X" → OVH.csv ✅ (largest invoices from vendor X)
- "Prodej samolepek" → Sales.csv ✅ (revenue from selling)
- "Kolik stojí samolepky na fakturách?" → OVH.csv ✅ (costs)
- "Kolik jsme prodali samolepek?" → Sales.csv ✅ (revenue)

**CRITICAL RULE:**
- **Default → ALWAYS USE PL.csv** (unless vendor/ELD/description explicitly mentioned)
- Only switch to OVH if user asks for: **vendor** OR **ELD** OR **document description** OR **"faktury"**
- "náklady střediska Finance" → PL.csv ✅ (no vendor/ELD mentioned)
- "dodavatelé střediska Finance" → OVH.csv ✅ (vendor mentioned!)
- "detail po ELD u střediska Finance" → OVH.csv ✅ (ELD mentioned!)
- "faktury s 'úklid' v ALZABOX" → OVH.csv ✅ (description mentioned!)
- "faktury obsahující 'samolepky'" → OVH.csv ✅ (faktury = invoice documents!)

**EXAMPLES:**

```python
# ✅ SPRÁVNĚ - Cost center query WITHOUT vendor:
"Náklady střediska Finance v lednu 2024"
→ USE PL.csv, filter CC-Level 1/2 = 'Finance'

# ✅ SPRÁVNĚ - Category query:
"Kolik je Personální náklady v roce 2024?"
→ USE PL.csv, filter Acc-Level 1 = 'Personální náklady'

# ✅ SPRÁVNĚ - Account query:
"Detail účtu 501 200"
→ USE PL.csv, filter Analytical account = '501 200'

# ✅ SPRÁVNĚ - Vendor query:
"Kolik jsme zaplatili firmě KPK?"
→ USE OVH.csv, filter Customer/company name LIKE 'KPK'

# ✅ SPRÁVNĚ - ELD query:
"Detail faktury ELD5724723"
→ USE OVH.csv, filter Electronic document key = 'ELD5724723'

# ✅ SPRÁVNĚ - Document description query:
"Faktury obsahující 'samolepky'"
→ USE OVH.csv, filter Document item description LIKE 'samolepky'

# ⚠️ KOMBINOVANÝ DOTAZ - ELD + Cost Center:
"Detail po ELD u střediska Finance v lednu 2024"
→ USE OVH.csv (because "ELD" is mentioned!)
→ Filter CC-Level 1/2 = 'Finance' in OVH
→ Show: ELD, Description, Vendor, Amount

# ✅ SPRÁVNĚ - Vendor + Cost Center:
"Dodavatelé v ALZABOX v roce 2024"
→ USE OVH.csv (because "dodavatelé" is mentioned!)
→ Filter CC-Level 1/2 = 'ALZABOX' in OVH
→ Group by Customer/company name

# ❌ ŠPATNĚ - Cost center query with OVH:
"Náklady střediska Finance v lednu 2024"
→ DO NOT USE OVH.csv! Use PL.csv instead!
→ No mention of vendor/ELD/description = PL.csv!

# ❌ ŠPATNĚ - Using Sales for expense invoices:
"Faktury obsahující 'samolepky' v roce 2024"
→ DO NOT USE Sales.csv! Use OVH.csv instead!
→ "Faktury" = expense invoices = OVH.csv!
→ Sales.csv is for REVENUE (tržby), not costs!
```

### 2. ACCOUNT CLASS FILTERING (MANDATORY):

**Account class column values:**
- **"5"** = Náklady (Expenses/Costs) ← PRIMARY USE
- **"6"** = Výnosy (Revenue) ← USE ONLY for specific account queries!

**CRITICAL RULES:**
- For "náklady", "costs", "expenses" → Filter Account class = 5 from PL.csv
- For "tržby", "revenue", "sales", "výnosy" (general) → USE BUSINESS MODULE (Sales.csv), NOT accounting!
- For "účet 6XXX" or "account 601" (specific accounting query) → Filter Account class = 6 from PL.csv

**Examples:**
```python
# ✅ General costs query:
"Celkové náklady v roce 2024" → Account class = 5

# ✅ General revenue query:
"Výnosy v roce 2024" → SWITCH TO BUSINESS MODULE (Sales.csv)

# ✅ Specific accounting account query:
"Kolik je na účtu 601 v lednu?" → Account class = 6, filter účet = 601

# ✅ Specific accounting account query:
"Detail účtu 6XXX v roce 2024" → Account class = 6, filter účet starts with '6'
```

**DEFAULT: ALWAYS filter Account class = 5 unless user asks for specific account starting with '6'!**

### 3. DATE HANDLING:

**PL.csv and OVH.csv DO NOT have 'Document date' column!**

These files have MONTHLY COLUMNS in format: '01.01.2024', '01.02.2024', '01.03.2024', etc.

```python
# ✅ SPRÁVNĚ - Get all 2024 costs:
pl_costs = PL[PL['Account class'] == '5'].copy()  # Filter costs first!
date_cols_2024 = [col for col in pl_costs.columns if '2024' in col]
total_2024 = pl_costs[date_cols_2024].sum().sum()

# ✅ SPRÁVNĚ - Get Q1 2024 costs:
pl_costs = PL[PL['Account class'] == '5'].copy()
q1_cols = ['01.01.2024', '01.02.2024', '01.03.2024']
q1_total = pl_costs[q1_cols].sum().sum()

# ✅ SPRÁVNĚ - Get June 2024 costs:
pl_costs = PL[PL['Account class'] == '5'].copy()
june_col = '01.06.2024'
june_total = pl_costs[june_col].sum()

# ❌ ŠPATNĚ - NEVER do this:
df_filtered = PL[PL['Document date'] == '2024-06-01']  # ← Column doesn't exist!
total = PL[date_cols].sum()  # ← Missing Account class filter!
```

### 4. NUMERIC DATA CLEANING (CRITICAL):

**PL.csv and OVH.csv format:**
- Separator: `;` (semicolon)
- Decimal: `,` (comma)
- Negative values: `-300,01`
- Empty cells: `;;;` (multiple semicolons)

**Numbers should already be numeric from DataManager, but verify!**

```python
# ✅ SPRÁVNĚ - Ensure numeric and handle edge cases:
def ensure_numeric_columns(df, date_columns):
    # Ensure date columns are numeric, handle any remaining string formats
    for col in date_columns:
        if col not in df.columns:
            continue
            
        # Check if already numeric
        if pd.api.types.is_numeric_dtype(df[col]):
            # Fill NaN with 0 for aggregation
            df[col] = df[col].fillna(0)
        else:
            # Convert from string format
            df[col] = df[col].astype(str).str.replace(' ', '').str.replace(',', '.')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    return df

# Use it ALWAYS for accounting data:
pl_costs = PL[PL['Account class'] == '5'].copy()
date_cols_2024 = [col for col in pl_costs.columns if '2024' in col]

# Ensure numeric BEFORE summing!
pl_costs = ensure_numeric_columns(pl_costs, date_cols_2024)

total_2024 = pl_costs[date_cols_2024].sum().sum()
```

**ALWAYS ensure numeric before any calculation!**

### 5. PERCENTAGE CALCULATION FOR ACCOUNTING:

**Accounting data has NEGATIVE values (costs are negative numbers)!**

```python
# ❌ ŠPATNĚ - Negative / Negative = positive, but percentages wrong:
category_breakdown['Podíl %'] = (category_breakdown['Náklady'] / total * 100)

# ✅ SPRÁVNĚ - Use absolute values for percentage:
category_breakdown['Abs_Value'] = category_breakdown['Náklady'].abs()
total_abs = category_breakdown['Abs_Value'].sum()
category_breakdown['Podíl %'] = (category_breakdown['Abs_Value'] / total_abs * 100).round(1)

# Then drop the temp column:
category_breakdown = category_breakdown.drop('Abs_Value', axis=1)
```

**ALWAYS use .abs() when calculating percentages for accounting data!**

### 6. TIME PERIOD QUERIES:

**For Q1/Q2/Q3/Q4 queries:**
```python
# Q1 = January, February, March
q1_cols = ['01.01.2024', '01.02.2024', '01.03.2024']

# Q2 = April, May, June
q2_cols = ['01.04.2024', '01.05.2024', '01.06.2024']

# Q3 = July, August, September
q3_cols = ['01.07.2024', '01.08.2024', '01.09.2024']

# Q4 = October, November, December
q4_cols = ['01.10.2024', '01.11.2024', '01.12.2024']
```

### 7. DATE COLUMN HANDLING:

**Monthly columns format: '01.01.2024', '01.02.2024', etc.**

```python
# Get all 2024 columns:
date_cols_2024 = [col for col in df.columns if '2024' in col]

# Get specific month:
jan_col = '01.01.2024'
june_col = '01.06.2024'

# Get year-to-date (YTD):
ytd_cols = [col for col in df.columns if '2024' in col and col <= '01.06.2024']
```

### 8. COST CENTER vs COST CATEGORY (CRITICAL DISTINCTION!):

**Two separate dimension types - DO NOT CONFUSE!**

**A) COST CENTER (Organizational structure):**
- Columns: `CC-Level 1`, `CC-Level 2`
- Examples: "ALZABOX", "Finance", "Marketing", "B2B", "IT"
- User queries: "středisko", "cost center", "oddělení", "tým"

**B) COST CATEGORY (Type of expense):**
- Columns: `Acc-Level 1`, `Acc-Level 2`, `Acc-Level 3`
- Examples: "Režijní náklady", "Reklama", "Personální náklady", "Finanční výnosy"
- User queries: "kategorie", "druh nákladu", "typ nákladu"

**ROBUST COST CENTER MATCHING STRATEGY:**

Use two-stage approach with diacritics removal to handle variations:

```python
from difflib import get_close_matches
import unicodedata

# Helper function to remove diacritics
def remove_diacritics(text):
    # Remove Czech diacritics using translation table
    if pd.isna(text):
        return ''
    text = str(text)
    
    # Czech diacritics mapping
    diacritics = {{
        'á': 'a', 'č': 'c', 'ď': 'd', 'é': 'e', 'ě': 'e',
        'í': 'i', 'ň': 'n', 'ó': 'o', 'ř': 'r', 'š': 's',
        'ť': 't', 'ú': 'u', 'ů': 'u', 'ý': 'y', 'ž': 'z',
        'Á': 'A', 'Č': 'C', 'Ď': 'D', 'É': 'E', 'Ě': 'E',
        'Í': 'I', 'Ň': 'N', 'Ó': 'O', 'Ř': 'R', 'Š': 'S',
        'Ť': 'T', 'Ú': 'U', 'Ů': 'U', 'Ý': 'Y', 'Ž': 'Z'
    }}
    
    for char, replacement in diacritics.items():
        text = text.replace(char, replacement)
    
    return text

# STAGE 1: Get unique cost centers from CC-Level columns ONLY
pl_costs = PL[PL['Account class'] == 5].copy()

unique_cc1 = pl_costs['CC-Level 1'].dropna().unique().tolist()
unique_cc2 = pl_costs['CC-Level 2'].dropna().unique().tolist()
all_cc = list(set(unique_cc1 + unique_cc2))

# Clean and prepare for matching
all_cc_clean = [str(x).strip() for x in all_cc if pd.notna(x)]

# User input
user_input = 'Nákup'  # From user query (with diacritics)
user_input_clean = user_input.strip()

# STAGE 2: Try exact match (case-insensitive, diacritics-insensitive)
cc_name = None
user_normalized = remove_diacritics(user_input_clean).lower()

for cc in all_cc_clean:
    cc_normalized = remove_diacritics(cc).lower()
    if cc_normalized == user_normalized:
        cc_name = cc  # Found match! (e.g., 'NAKUP')
        break

# STAGE 3: If no exact match, try fuzzy matching with normalized strings
if not cc_name:
    # Normalize all options
    all_cc_normalized = [remove_diacritics(cc).lower() for cc in all_cc_clean]
    
    # Fuzzy match
    matches = get_close_matches(user_normalized, all_cc_normalized, n=1, cutoff=0.85)
    
    if matches:
        # Find original (non-normalized) name
        idx = all_cc_normalized.index(matches[0])
        cc_name = all_cc_clean[idx]

# STAGE 4: Use result
if cc_name:
    finance_center = pl_costs[
        (pl_costs['CC-Level 1'] == cc_name) |
        (pl_costs['CC-Level 2'] == cc_name)
    ].copy()
else:
    # No match found - inform user
    result = pd.DataFrame({{
        'Chyba': [f'Cost centrum "{user_input}" nenalezeno. Dostupná střediska: {{", ".join(sorted(all_cc_clean)[:10])}}...'],
        'Hodnota': [0]
    }})
```

**WHY THIS WORKS:**
1. ✅ **Remove diacritics**: "Nákup" → "nakup", "NÁKUP" → "nakup"
2. ✅ **Case-insensitive**: "nakup" == "NAKUP".lower()
3. ✅ **Exact match first**: "Nákup" → "NAKUP" (perfect match)
4. ✅ **Fuzzy for typos**: "Nakuup" → "NAKUP" (similarity ~0.9)
5. ✅ **High cutoff (0.85)**: Avoids false positives

**EXAMPLES:**
- "Nákup" → "NAKUP" ✅ (diacritics removed, case-insensitive)
- "nakup" → "NAKUP" ✅ (case-insensitive)
- "NAKUP" → "NAKUP" ✅ (exact)
- "Nákuup" → "NAKUP" ✅ (fuzzy match)
- "Finance" vs "Finanční" → NO match ✅ (below cutoff)

**SIMILARITY SCORES (after normalization):**
- "nakup" vs "NAKUP" = 1.0 ✅
- "Nakuup" vs "NAKUP" = 0.88 ✅
- "Nakp" vs "NAKUP" = 0.80 ❌ (below 0.85 cutoff)
- "Finance" vs "Financni" = 0.70 ❌

**ALTERNATIVE (simpler but less precise):**
```python
# If you don't want to use difflib, use partial match with validation:
cc_filter = pl_costs[
    pl_costs['CC-Level 1'].str.contains('Financ', case=False, na=False)
].copy()

# Then validate it's reasonable (not mixing with categories)
if len(cc_filter) == 0:
    # Try CC-Level 2
    cc_filter = pl_costs[
        pl_costs['CC-Level 2'].str.contains('Financ', case=False, na=False)
    ].copy()
```

### 9. COST CENTER QUERY OUTPUT STRUCTURE:

**CRITICAL: Only include CC-Level columns when user explicitly asks for cost center!**

**COST CENTER KEYWORDS:**
- "středisko", "cost centrum", "cost center", "tým", "útvar", "department", "oddělení"

**IF user mentions cost center keyword:**
```python
# User: "Náklady střediska Finance v lednu 2024"
# Group by: ['CC-Level 1', 'Acc-Level 1']  ← Note: NO CC-Level 2!
result = df.groupby(['CC-Level 1', 'Acc-Level 1'])[date_cols].sum()
```

**IF user does NOT mention cost center:**
```python
# User: "Režijní náklady v lednu 2024"  ← NO středisko mentioned!
# Group by: ['Acc-Level 1'] only (or ['Acc-Level 2'] for subcategories)
result = df.groupby('Acc-Level 2')[date_cols].sum()  # ← Just categories!
```

**EXAMPLES:**

**A) NO COST CENTER MENTIONED:**
```python
# Query: "Režijní náklady v lednu 2024"
# ❌ ŠPATNĚ - Včetně CC-Level:
result = pl.groupby(['CC-Level 1', 'CC-Level 2', 'Acc-Level 2'])[jan_col].sum()

# ✅ SPRÁVNĚ - Pouze kategorie:
rezijni = pl[pl['Acc-Level 1'].str.contains('Režijní', case=False, na=False)].copy()
result = rezijni.groupby('Acc-Level 2')[jan_col].sum().reset_index()
result.columns = ['Podkategorie', 'Režijní náklady leden 2024']
```

**B) COST CENTER MENTIONED:**
```python
# Query: "Náklady střediska Finance v lednu 2024"
# ✅ SPRÁVNĚ - Include CC-Level 1 ONLY (not CC-Level 2):
finance = pl[(pl['CC-Level 1'] == 'FINANCE')].copy()
result = finance.groupby(['CC-Level 1', 'Acc-Level 1'])[jan_col].sum()
```

**MANDATORY BASE STRUCTURE (when středisko mentioned):**
Always include these columns (in order):
1. CC-Level 1 (cost center - top level only)
2. Kategorie nákladů (= Acc-Level 1 or Acc-Level 2 depending on detail needed)

**NOTE: CC-Level 2 is NOT included in output tables (removed for simplicity)**

**DYNAMIC COLUMNS based on user request:**

**A) SINGLE PERIOD (one month/quarter/year total):**
```python
['CC-Level 1', 'Kategorie nákladů', 'Náklady leden 2024', 'Podíl %']
```

**B) TIME SERIES (multiple months):**
```python
['CC-Level 1', 'Kategorie nákladů', 'Leden', 'Únor', 'Březen', ..., 'CELKEM']
```

**C) ANNUAL WITH TREND:**
```python
['CC-Level 1', 'Kategorie nákladů', 'Leden', ..., 'Prosinec', 'CELKEM 2024', 'YoY %']
```

**Example A: "Náklady střediska Finance v lednu 2024"**

```python
# After cost center matching...
finance_center = pl_costs[
    (pl_costs['CC-Level 1'] == 'FINANCE') |
    (pl_costs['CC-Level 2'] == 'FINANCE')
].copy()

jan_col = '01.01.2024'
finance_center = ensure_numeric_columns(finance_center, [jan_col])

# Group by CC-Level 1 and Acc-Level 1 (NO CC-Level 2!)
result = finance_center.groupby(['CC-Level 1', 'Acc-Level 1'])[jan_col].sum().reset_index()
result.columns = ['CC-Level 1', 'Kategorie nákladů', 'Náklady leden 2024']

# Sort and add percentages
result['Abs_Value'] = result['Náklady leden 2024'].abs()
result = result.sort_values('Abs_Value', ascending=False)
total_abs = result['Abs_Value'].sum()
result['Podíl %'] = (result['Abs_Value'] / total_abs * 100).round(1)
result = result[['CC-Level 1', 'Kategorie nákladů', 'Náklady leden 2024', 'Podíl %']]

# Add CELKEM
total = result['Náklady leden 2024'].sum()
celkem_row = pd.DataFrame({{
    'CC-Level 1': ['CELKEM'],
    'Kategorie nákladů': [''],
    'Náklady leden 2024': [total],
    'Podíl %': [100.0]
}})
result = pd.concat([result, celkem_row], ignore_index=True)
```

**Example B: "Režijní náklady střediska Finance po měsících v roce 2024"**

```python
# After cost center matching...
finance_center = pl_costs[
    (pl_costs['CC-Level 1'] == 'FINANCE') |
    (pl_costs['CC-Level 2'] == 'FINANCE')
].copy()

# Filter for Režijní náklady category
finance_center = finance_center[
    finance_center['Acc-Level 1'].str.contains('Režijní', case=False, na=False)
].copy()

# Get all 2024 monthly columns
date_cols_2024 = [col for col in finance_center.columns if '2024' in col]
finance_center = ensure_numeric_columns(finance_center, date_cols_2024)

# Group by CC-Level 1 and Acc-Level 1 (NO CC-Level 2!)
monthly_data = finance_center.groupby(['CC-Level 1', 'Acc-Level 1'])[date_cols_2024].sum().reset_index()

# Rename date columns to month names
month_names = ['Leden', 'Únor', 'Březen', 'Duben', 'Květen', 'Červen', 
               'Červenec', 'Srpen', 'Září', 'Říjen', 'Listopad', 'Prosinec']
col_mapping = dict(zip(date_cols_2024, month_names[:len(date_cols_2024)]))
monthly_data = monthly_data.rename(columns=col_mapping)

# Add CELKEM column (sum across months)
monthly_data['CELKEM'] = monthly_data[month_names[:len(date_cols_2024)]].sum(axis=1)

# Add CELKEM row
celkem_row = pd.DataFrame({{
    'CC-Level 1': ['CELKEM'],
    'Kategorie nákladů': ['']
}})
for month in month_names[:len(date_cols_2024)]:
    celkem_row[month] = [monthly_data[month].sum()]
celkem_row['CELKEM'] = [monthly_data['CELKEM'].sum()]

result = pd.concat([monthly_data, celkem_row], ignore_index=True)
```

**OUTPUT A (single period):**
```
CC-Level 1 | Kategorie nákladů | Náklady leden 2024 | Podíl %
FINANCE    | Režijní náklady   | -8 154 662         | 45.2%
FINANCE    | Personální        | -5 000 000         | 27.7%
CELKEM     |                   | -18 116 835        | 100.0%
```

**OUTPUT B (time series):**
```
CC-Level 1 | Kategorie | Leden    | Únor     | Březen   | ... | CELKEM
FINANCE    | Režijní   | -8154662 | -7500000 | -9200000 | ... | -98500000
CELKEM     |           | -8154662 | -7500000 | -9200000 | ... | -98500000
```

**KEY RULES:**
- ✅ Always start with: CC-Level 1, Kategorie nákladů (NO CC-Level 2!)
- ✅ For single period: add value + percentage
- ✅ For time series: add monthly columns + CELKEM
- ✅ Always add CELKEM row at the bottom

**EXAMPLES:**

```python
# ✅ SPRÁVNĚ - User asks about cost CENTER (robust matching with diacritics):
"Náklady střediska Nákup v lednu 2024"

from difflib import get_close_matches
import pandas as pd
import unicodedata

def remove_diacritics(text):
    if pd.isna(text):
        return ''
    text = str(text)
    nfd = unicodedata.normalize('NFD', text)
    return ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')

pl_costs = PL[PL['Account class'] == 5].copy()

# Get unique cost centers from CC-Level columns ONLY
unique_cc1 = pl_costs['CC-Level 1'].dropna().unique().tolist()
unique_cc2 = pl_costs['CC-Level 2'].dropna().unique().tolist()
all_cc = list(set(unique_cc1 + unique_cc2))
all_cc_clean = [str(x).strip() for x in all_cc if pd.notna(x)]

# User input
user_input = 'Nákup'
user_input_clean = user_input.strip()

# Stage 1: Try exact match (case + diacritics insensitive)
cc_name = None
user_normalized = remove_diacritics(user_input_clean).lower()

for cc in all_cc_clean:
    cc_normalized = remove_diacritics(cc).lower()
    if cc_normalized == user_normalized:
        cc_name = cc  # e.g., 'NAKUP'
        break

# Stage 2: Fuzzy match if no exact match
if not cc_name:
    all_cc_normalized = [remove_diacritics(cc).lower() for cc in all_cc_clean]
    matches = get_close_matches(user_normalized, all_cc_normalized, n=1, cutoff=0.85)
    if matches:
        idx = all_cc_normalized.index(matches[0])
        cc_name = all_cc_clean[idx]

# Stage 3: Use result with proper output structure
if cc_name:
    finance_center = pl_costs[
        (pl_costs['CC-Level 1'] == cc_name) |
        (pl_costs['CC-Level 2'] == cc_name)
    ].copy()
    
    # Ensure numeric
    finance_center = ensure_numeric_columns(finance_center, date_cols)
    
    # Group by CC-Level 1 and Acc-Level 1 (NO CC-Level 2!)
    result = finance_center.groupby(['CC-Level 1', 'Acc-Level 1'])[date_cols].sum().sum(axis=1).reset_index()
    result.columns = ['CC-Level 1', 'Kategorie nákladů', 'Náklady']
    
    # Sort and add percentages
    result['Abs_Value'] = result['Náklady'].abs()
    result = result.sort_values('Abs_Value', ascending=False)
    result['Podíl %'] = (result['Abs_Value'] / result['Abs_Value'].sum() * 100).round(1)
    result = result[['CC-Level 1', 'Kategorie nákladů', 'Náklady', 'Podíl %']]
else:
    result = pd.DataFrame({{
        'Chyba': [f'Cost centrum "{user_input}" nenalezeno'],
        'Hodnota': [0]
    }})

# ✅ SPRÁVNĚ - User asks about cost CATEGORY:
"Kolik je v kategorii Personální náklady?"

pl_costs = PL[PL['Account class'] == 5].copy()

# Filter by COST CATEGORY columns only!
personnel = pl_costs[
    (pl_costs['Acc-Level 1'].str.contains('Personální', case=False, na=False)) |
    (pl_costs['Acc-Level 2'].str.contains('Personální', case=False, na=False))
].copy()

# ❌ ŠPATNĚ - Mixing cost center and category:
"Náklady střediska Finance"
→ Filters Acc-Level 1 containing "Finanční výnosy"  # ← WRONG!
→ Should filter CC-Level 1/2 for "Finance"  # ← CORRECT!
```

**KEYWORDS FOR DETECTION:**
- Cost CENTER keywords: "středisko", "cost center", "cost centrum", "oddělení", "tým", "útvar", "department"
- Cost CATEGORY keywords: "kategorie", "druh", "typ", "kind of expense", "type of cost"

**GROUPING RULES:**
- If user mentions cost CENTER keyword → Group by ['CC-Level 1', 'CC-Level 2', 'Acc-Level']
- If NO cost center keyword → Group by ['Acc-Level'] ONLY!
- Never add CC-Level columns unless explicitly asked!

**EXAMPLES:**
- "Režijní náklady v lednu" → Group by Acc-Level ONLY ✅
- "Náklady střediska Finance" → Group by CC + Acc-Level ✅
- "Personální náklady po měsících" → Group by Acc-Level ONLY ✅
- "Finance breakdown" → Group by CC + Acc-Level ✅

### 10. VENDOR SEARCH (OVH.csv):

**CRITICAL: OVH.csv is in WIDE FORMAT (like PL.csv)!**
- Monthly columns: '01.01.2024', '01.02.2024', '01.03.2024', ...
- NO 'Document date' or 'Amount' column!
- Each row = one invoice line item (ELD) with values spread across months

**When user asks about specific vendor/supplier:**
- "Kolik jsme zaplatili firmě KPK?" 
- "Dodavatel XYZ"
- "Vendor ABC"
- "Top 10 faktur společnosti X"

**A) VENDOR TOTAL (sum across time):**

```python
# Query: "Kolik jsme zaplatili firmě KPK v roce 2024?"

ovh = OVH.copy()

# Get date columns
date_cols_2024 = [col for col in ovh.columns if '2024' in col]

# Ensure numeric
ovh = ensure_numeric_columns(ovh, date_cols_2024)

# LIKE search for vendor name
ovh_filtered = ovh[ovh['Customer/company name'].str.contains('KPK', case=False, na=False)].copy()

# Group by category AND vendor, sum across all months
vendor_breakdown = ovh_filtered.groupby(['Acc-Level 1', 'Customer/company name'])[date_cols_2024].sum().sum(axis=1).reset_index()
vendor_breakdown.columns = ['Kategorie', 'Dodavatel', 'Platba KPK 2024']

# Sort by absolute value
vendor_breakdown['Abs_Value'] = vendor_breakdown['Platba KPK 2024'].abs()
vendor_breakdown = vendor_breakdown.sort_values('Abs_Value', ascending=False)
vendor_breakdown = vendor_breakdown[['Kategorie', 'Dodavatel', 'Platba KPK 2024']]

result = vendor_breakdown
```

**B) TOP INVOICES (individual line items):**

```python
# Query: "Top 10 faktur společnosti Direct Parcel v roce 2025"

ovh = OVH.copy()

# STEP 1: Get monthly columns for 2025
date_cols_2025 = [col for col in ovh.columns if '2025' in col]

# STEP 2: Ensure numeric
for col in date_cols_2025:
    ovh[col] = pd.to_numeric(ovh[col], errors='coerce').fillna(0)

# STEP 3: Filter vendor
ovh_filtered = ovh[ovh['Customer/company name'].str.contains('Direct Parcel', case=False, na=False)].copy()

# STEP 4: Sum each row across all 2025 months
# Each row = one invoice line item (ELD + description)
ovh_filtered['Celková částka 2025'] = ovh_filtered[date_cols_2025].sum(axis=1)

# STEP 5: Sort by absolute value (costs are negative)
ovh_filtered['Abs_Value'] = ovh_filtered['Celková částka 2025'].abs()
ovh_filtered = ovh_filtered.sort_values('Abs_Value', ascending=False)

# STEP 6: Take top 10 rows
top_10 = ovh_filtered.head(10)

# STEP 7: Select and rename columns
result = top_10[['Electronic document key', 'Document item description', 'Customer/company name', 'Celková částka 2025']].copy()
result.columns = ['ELD', 'Popis', 'Dodavatel', 'Částka 2025']

# Result shows top 10 invoice LINE ITEMS (not grouped, each row is separate)
```

**CRITICAL NOTES:**
- DO NOT use 'Invoice date' or 'Document date' - these columns DON'T EXIST!
- DO NOT use 'Amount' column - it DOESN'T EXIST!
- ALWAYS sum across monthly columns: `df[date_cols].sum(axis=1)`
- Each row in OVH = one invoice line item
- For top invoices: sum per row, then sort and take top N
```

**KEY POINTS:**
- OVH is WIDE format - sum across monthly columns!
- NO 'Document date' column - use monthly columns ('01.01.2025', ...)
- Each row = one invoice line item
- For totals: group and sum
- For top invoices: sum per row, then sort

**CRITICAL: Show ALL matching vendors separately, not grouped!**

### 11. COMPLETE EXAMPLE - "Celkové náklady v roce 2024":

```python
import pandas as pd
import numpy as np

# Helper function for numeric handling
def ensure_numeric_columns(df, date_columns):
    # Ensure date columns are numeric
    for col in date_columns:
        if col not in df.columns:
            continue
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(0)
        else:
            df[col] = df[col].astype(str).str.replace(' ', '').str.replace(',', '.')
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

# 1. Load PL data (NOT OVH!)
pl = PL.copy()

# 2. Filter for COSTS ONLY (Account class = '5')
# DEBUG: Print Account class info
print(f"DEBUG: Account class unique values: {pl['Account class'].unique()}")
print(f"DEBUG: Account class dtype: {pl['Account class'].dtype}")

# Try both string and int filter
pl_costs_str = pl[pl['Account class'] == '5'].copy()
pl_costs_int = pl[pl['Account class'] == 5].copy()

print(f"DEBUG: Rows with Account class == '5' (string): {len(pl_costs_str)}")
print(f"DEBUG: Rows with Account class == 5 (int): {len(pl_costs_int)}")

# Use whichever has data
if len(pl_costs_str) > 0:
    pl_costs = pl_costs_str
elif len(pl_costs_int) > 0:
    pl_costs = pl_costs_int
else:
    # No costs found - create error result and exit
    result = pd.DataFrame({{
        'Kategorie': ['CHYBA: Žádné náklady nenalezeny'],
        'Náklady 2024': [0],
        'Podíl %': [0]
    }})
    # Note: This will be the final result, code below won't execute

# Only continue if we have costs data
if len(pl_costs) > 0:
    # 3. Get all 2024 date columns
    date_cols_2024 = [col for col in pl_costs.columns if '2024' in col]

    # 4. Ensure numeric (CRITICAL!)
    pl_costs = ensure_numeric_columns(pl_costs, date_cols_2024)

    # 5. Sum across all 2024 months
    total_costs_2024 = pl_costs[date_cols_2024].sum().sum()

    # 6. Breakdown by category
    category_breakdown = pl_costs.groupby('Acc-Level 1')[date_cols_2024].sum().sum(axis=1).reset_index()
    category_breakdown.columns = ['Kategorie', 'Náklady 2024']

    # IMPORTANT: Use absolute values for percentage calculation (costs are negative!)
    category_breakdown['Abs_Value'] = category_breakdown['Náklady 2024'].abs()
    category_breakdown = category_breakdown.sort_values('Abs_Value', ascending=False)

    # 7. Calculate percentages based on absolute values
    total_abs = category_breakdown['Abs_Value'].sum()
    if total_abs > 0:
        category_breakdown['Podíl %'] = (category_breakdown['Abs_Value'] / total_abs * 100).round(1)
    else:
        category_breakdown['Podíl %'] = 0.0

    # Drop temporary column
    category_breakdown = category_breakdown[['Kategorie', 'Náklady 2024', 'Podíl %']]

    # 8. Add CELKEM row
    total = category_breakdown['Náklady 2024'].sum()
    celkem_row = pd.DataFrame({{
        'Kategorie': ['CELKEM'],
        'Náklady 2024': [total],
        'Podíl %': [100.0]
    }})
    result = pd.concat([category_breakdown, celkem_row], ignore_index=True)
```

**REMEMBER:**
- Account class 5 = Costs/Expenses (DEFAULT - use for "náklady" queries)
- Account class 6 = Revenue (use ONLY for specific account queries like "účet 601")
- For general revenue queries ("výnosy", "tržby") → USE BUSINESS MODULE!
- ALWAYS convert numbers from string format BEFORE calculations!
- **DEFAULT dataset: PL.csv** (aggregated costs/revenue)
- Switch to OVH.csv ONLY when user explicitly asks for vendor/ELD/document description!
- For cost center/category queries WITHOUT vendor → USE PL.csv!
- For vendor queries: Group by ['Category', 'Customer/company name'] to show EACH vendor separately!
"""
    else:
        module_name = "BUSINESS"
        date_handling_instructions = """
## ⚠️ CRITICAL: BUSINESS MODULE - DATE HANDLING

**Sales.csv has WIDE FORMAT with date columns!**

See section "1. PRÁCE S SALES.CSV (WIDE FORMAT)" below for detailed instructions.
Sales.csv requires UNPIVOT (melt) operation first.
"""
    
    prompt = f"""Jsi expert na datovou analýzu a Python/pandas. Tvým úkolem je vygenerovat čistý, funkční Python kód pro analýzu dat podle požadavku uživatele.

# 🎯 ACTIVE MODULE: {module_name}
{date_handling_instructions}

# UŽIVATELSKÝ POŽADAVEK:
{user_request}

# DOSTUPNÉ DATASETY:
{datasets_info}

Dostupné proměnné v prostředí: {', '.join(available_dataframes)}

# KRITICKÁ INFORMACE O STRUKTUŘE DAT:
{format_data_structure_info(data_structure_info)}

# DEFINICE SLOUPCŮ:
{format_column_definitions(column_definitions)}

# BUSINESS PRAVIDLA:
{format_alza_specific_rules(alza_specific_rules)}

# CRITICAL: PRAVIDLA PRO GENEROVÁNÍ KÓDU

## 1. PRÁCE S SALES.CSV (WIDE FORMAT):
⚠️ **Sales.csv má WIDE formát - datumy jsou sloupce (01.01.2024, 01.02.2024, ...)**

### MANDATORY POSTUP PRO SALES.CSV:

```python
import pandas as pd
import numpy as np

# 1. Načti Sales data
df = Sales.copy()

# 2. Identifikuj datumové sloupce (DD.MM.YYYY formát)
date_cols = [col for col in df.columns if '.' in col and any(char.isdigit() for char in col)]

# 3. Identifikuj dimenze (non-date sloupce)
dimension_cols = [col for col in df.columns if col not in date_cols]

# 4. UNPIVOT (melt) - převeď WIDE → LONG formát
df_long = df.melt(
    id_vars=dimension_cols,
    value_vars=date_cols,
    var_name='Datum',
    value_name='Tržby'
)

# 5. Vyčisti data
df_long = df_long[df_long['Tržby'].notna()].copy()  # Odstraň NaN
df_long['Tržby'] = pd.to_numeric(df_long['Tržby'], errors='coerce')  # Konverze na numeric
df_long = df_long[df_long['Tržby'] != 0].copy()  # Odstraň nuly

# 6. Převeď datum na datetime
df_long['Datum'] = pd.to_datetime(df_long['Datum'], format='%d.%m.%Y', errors='coerce')
df_long = df_long[df_long['Datum'].notna()].copy()

# NYNÍ MÁŠ LONG FORMAT A MŮŽEŠ POKRAČOVAT S ANALÝZOU!
```

### FILTROVÁNÍ OBDOBÍ:
```python
# Pro červen 2025:
df_filtered = df_long[
    (df_long['Datum'].dt.year == 2025) & 
    (df_long['Datum'].dt.month == 6)
].copy()

# Pro období od-do:
df_filtered = df_long[
    (df_long['Datum'] >= '2024-01-01') & 
    (df_long['Datum'] <= '2025-05-31')
].copy()
```

### AGREGACE PO UNPIVOT:
```python
# Group by platební metoda:
result = df_filtered.groupby('Payment detail name').agg({{
    'Tržby': 'sum'  # ← SUM tržeb, NE count!
}}).reset_index()

# Seřaď sestupně (nejvyšší nahoře):
result = result.sort_values('Tržby', ascending=False).reset_index(drop=True)

# Přidej podíl %:
total = result['Tržby'].sum()
result['Podíl %'] = (result['Tržby'] / total * 100).round(1)

# Přidej CELKEM řádek:
celkem_row = pd.DataFrame({{
    'Payment detail name': ['CELKEM'],
    'Tržby': [result['Tržby'].sum()],
    'Podíl %': [100.0]
}})
result = pd.concat([result, celkem_row], ignore_index=True)
```

## 2. ŘAZENÍ VÝSLEDKŮ:
⚠️ **VŽDY řaď od nejvyšší hodnoty k nejnižší (ascending=False)**
- Top N položek = highest values first
- Bottom položky zobrazuj EXPLICITNĚ pouze pokud uživatel řekne "bottom" nebo "nejnižší"

```python
# ✅ SPRÁVNĚ - nejvyšší nahoře:
result = result.sort_values('Tržby', ascending=False)

# ❌ ŠPATNĚ - nejnižší nahoře:
result = result.sort_values('Tržby', ascending=True)
```

## 3. MĚSÍČNÍ VÝVOJE (MANDATORY):
Pro jakýkoliv "vývoj", "trend", "měsíční" požadavek **VŽDY přidej YoY % a MoM %**:

```python
# Po UNPIVOT a přípravě dat:
df_long['Období'] = df_long['Datum'].dt.to_period('M')

# Měsíční agregace:
monthly = df_long.groupby('Období').agg({{
    'Tržby': 'sum'
}}).reset_index()
monthly = monthly.sort_values('Období').reset_index(drop=True)

# MoM % (month-over-month):
monthly['MoM %'] = ((monthly['Tržby'] / monthly['Tržby'].shift(1)) - 1) * 100
monthly.loc[0, 'MoM %'] = 0  # První měsíc

# YoY % (year-over-year):
monthly['Rok'] = monthly['Období'].dt.year
monthly['Měsíc'] = monthly['Období'].dt.month

# Merge s minulým rokem:
monthly_prev = monthly[['Rok', 'Měsíc', 'Tržby']].copy()
monthly_prev['Rok'] = monthly_prev['Rok'] + 1
monthly_prev = monthly_prev.rename(columns={{'Tržby': 'Tržby_prev'}})

monthly = monthly.merge(monthly_prev, on=['Rok', 'Měsíc'], how='left')
monthly['YoY %'] = ((monthly['Tržby'] / monthly['Tržby_prev']) - 1) * 100
monthly['YoY %'] = monthly['YoY %'].fillna(0)

# Finální formát:
monthly['Období'] = monthly['Období'].astype(str)
result = monthly[['Období', 'Tržby', 'MoM %', 'YoY %']].copy()
```

## 4. DATOVÉ TYPY A BEZPEČNOST:
- NIKDY nepouživej .round() na sloupce s dtype 'object'
- VŽDY zkontroluj dtype před numerickými operacemi
- Pro konverzi: `pd.to_numeric(df[col], errors='coerce')`
- Formátuj čísla POUZE v posledním kroku
- Během výpočtů zachovej numeric typy

## 5. STRUKTURA KÓDU:
- Použij pouze dostupné DataFrames: {', '.join(available_dataframes)}
- Mezivýpočty ukládej do pojmenovaných proměnných
- Finální výsledek MUSÍ být v proměnné 'result'
- Nepřidávej print() kromě debuggu
- Používej descriptive názvy proměnných

## 6. PANDAS BEST PRACTICES:
- Filtrování: `.loc[]` místo chain indexing
- Agregace: `.groupby()` s `.agg()`
- Merge: `.merge()` s explicitními parametry
- Vždy `.copy()` při vytváření nového DataFrame
- Datumy: `pd.to_datetime()` s `errors='coerce'`

## 7. FORMÁTOVÁNÍ VÝSTUPU:
- Result = pandas DataFrame nebo Series
- Sloupce pojmenuj česky a srozumitelně
- Datumy: 'DD.MM.YYYY' nebo 'MM/YYYY'
- Číselné hodnoty jako numeric (ne string)
- Procenta v samostatném sloupci

## 8. CHYBOVÉ STAVY:
- Kontroluj neprázdný výsledek: `len(result) > 0`
- Ošetři missing values: `.fillna()` nebo `.dropna()`
- Division by zero: `.replace([np.inf, -np.inf], np.nan)`
- Pokud chybí data, vytvoř prázdný DataFrame

## 9. AGREGACE A SOUČTY:
- Pro součty: `.sum()`
- Pro průměry: `.mean()`
- Přidej řádek 'CELKEM' na konec
- CELKEM = poslední řádek DataFrame

## 10. CO NEDĚLAT:
❌ NIKDY neformátuj čísla na stringy během výpočtů
❌ NIKDY nepouživej .round() bez kontroly dtype
❌ NIKDY nevracej result jako dict nebo list
❌ NIKDY nepouživej deprecated pandas metody
❌ NIKDY nemodifikuj originální DataFrames
❌ NIKDY nezapomeň na UNPIVOT pro Sales.csv
❌ NIKDY neřaď ascending=True pokud uživatel nechce bottom values

## 11. KOMPLETNÍ PŘÍKLAD - "Platební metody v červnu 2025":

```python
import pandas as pd
import numpy as np

# 1. UNPIVOT Sales data
df = Sales.copy()
date_cols = [col for col in df.columns if '.' in col and any(char.isdigit() for char in col)]
dimension_cols = [col for col in df.columns if col not in date_cols]

df_long = df.melt(
    id_vars=dimension_cols,
    value_vars=date_cols,
    var_name='Datum',
    value_name='Tržby'
)

# 2. Vyčisti a připrav data
df_long = df_long[df_long['Tržby'].notna()].copy()
df_long['Tržby'] = pd.to_numeric(df_long['Tržby'], errors='coerce')
df_long = df_long[df_long['Tržby'] != 0].copy()
df_long['Datum'] = pd.to_datetime(df_long['Datum'], format='%d.%m.%Y', errors='coerce')
df_long = df_long[df_long['Datum'].notna()].copy()

# 3. Filtruj červen 2025
df_filtered = df_long[
    (df_long['Datum'].dt.year == 2025) & 
    (df_long['Datum'].dt.month == 6)
].copy()

# 4. Agreguj podle platební metody - SUM tržeb!
payment_analysis = df_filtered.groupby('Payment detail name').agg({{
    'Tržby': 'sum'
}}).reset_index()

# 5. Seřaď sestupně (nejvyšší nahoře)
payment_analysis = payment_analysis.sort_values('Tržby', ascending=False).reset_index(drop=True)

# 6. Přidej podíl %
total_revenue = payment_analysis['Tržby'].sum()
payment_analysis['Podíl %'] = (payment_analysis['Tržby'] / total_revenue * 100).round(1)

# 7. Přejmenuj sloupce
payment_analysis = payment_analysis.rename(columns={{
    'Payment detail name': 'Platební metoda'
}})

# 8. Přidej CELKEM řádek
celkem_row = pd.DataFrame({{
    'Platební metoda': ['CELKEM'],
    'Tržby': [payment_analysis['Tržby'].sum()],
    'Podíl %': [100.0]
}})
result = pd.concat([payment_analysis, celkem_row], ignore_index=True)
```

## 12. FORBIDDEN PATTERNS (NEVER USE THESE!):

**❌ NEVER use Sales.csv for "faktury" queries:**
```python
# ❌ ŠPATNĚ - User asked about EXPENSE invoices!
"Faktury obsahující 'samolepky' v roce 2024"
df = Sales.copy()  # ← WRONG! Sales is for REVENUE!

# ✅ SPRÁVNĚ - Use OVH for expense invoices:
df = OVH.copy()  # ← CORRECT! OVH has invoice details!
```

**CRITICAL RULE:**
- "faktury" in cost/expense context → OVH.csv ✅
- "faktury společnosti X" → OVH.csv ✅ (invoices FROM vendor X!)
- "prodej" or "tržby" → Sales.csv ✅
- NEVER confuse these two!

**❌ NEVER use Sales.csv for vendor invoice queries:**
```python
# ❌ ŠPATNĚ - User asked about vendor invoices!
"Top 10 faktur společnosti Direct Parcel Distribution"
df = Sales.copy()  # ← WRONG! This is for revenue, not vendor costs!

# ✅ SPRÁVNĚ - Use OVH for vendor invoices:
df = OVH.copy()
df = df[df['Customer/company name'].str.contains('Direct Parcel', case=False, na=False)]
```

**❌ NEVER invent columns that don't exist:**
```python
# ❌ ŠPATNĚ - These columns DO NOT EXIST in OVH!
df['Invoice date']  # ← NO! OVH has monthly columns, not 'Invoice date'!
df['Amount']        # ← NO! OVH has '01.01.2024', '01.02.2024', etc.
df['Document date'] # ← NO! Use monthly columns instead!

# ✅ SPRÁVNĚ - Use actual monthly columns:
date_cols_2025 = [col for col in df.columns if '2025' in col]
df['Total'] = df[date_cols_2025].sum(axis=1)  # Sum across months!
```

**CRITICAL: OVH is WIDE format - NO 'Invoice date' or 'Amount' columns!**

**❌ NEVER use this pattern:**
```python
# ❌ ŠPATNĚ - This breaks the code flow!
if 'result' not in locals():
    # ... code ...
    result = ...

# This pattern causes "None" returns because:
# - If error path creates 'result', this block is skipped
# - Result stays as error message instead of real data
```

**✅ ALWAYS use this pattern instead:**
```python
# ✅ SPRÁVNĚ - Clear control flow:
if len(filtered_data) > 0:
    # ... process data ...
    result = ...
else:
    # Create error result
    result = pd.DataFrame({{'Error': ['No data found']}})
```

**CRITICAL: Never check `if 'result' not in locals()` - it breaks everything!**

## 12. CROSS-MODULE QUERIES (Combining Accounting + Business):

**TRIGGER KEYWORDS for cross-module analysis:**
- "podíl ... na obratu" / "share of revenue"
- "jako % tržeb" / "as % of sales"
- "náklady vs tržby" / "costs vs revenue"
- "cost-to-revenue ratio"
- "marže" / "margin"
- "rentabilita" / "profitability"

**When user asks for RATIOS or COMPARISONS between costs and revenue:**

**When user asks for RATIOS or COMPARISONS between costs and revenue:**

Examples:
- "Podíl režijních nákladů na obratu"
- "Náklady střediska X jako % tržeb"
- "Cost-to-revenue ratio"
- "Marže po odečtení nákladů Y"

**STRATEGY:**
1. Calculate COSTS from PL.csv or OVH.csv
2. Calculate REVENUE from Sales.csv
3. Compute ratio/percentage
4. Return combined result

**EXAMPLE: "Podíl režijních nákladů financí na celkovém obratu v lednu 2024"**

```python
import pandas as pd
import numpy as np

# PART 1: Get regime costs from Finance cost center (PL.csv)
pl = PL.copy()
pl_costs = pl[pl['Account class'] == 5].copy()

# Filter Finance + Regime category
finance = pl_costs[
    (pl_costs['CC-Level 1'].str.contains('FINANCE', case=False, na=False)) &
    (pl_costs['Acc-Level 1'].str.contains('Režijní', case=False, na=False))
].copy()

jan_col = '01.01.2024'
finance[jan_col] = pd.to_numeric(finance[jan_col], errors='coerce').fillna(0)
rezijni_finance = finance[jan_col].sum()  # e.g., -10_000_000

# PART 2: Get total revenue from Sales.csv
sales = Sales.copy()
date_cols = [col for col in sales.columns if '.' in col and any(char.isdigit() for char in col)]

# Melt to long format
sales_long = sales.melt(
    id_vars=[col for col in sales.columns if col not in date_cols],
    value_vars=date_cols,
    var_name='Datum',
    value_name='Tržby'
)

sales_long['Tržby'] = pd.to_numeric(sales_long['Tržby'], errors='coerce')
sales_long['Datum'] = pd.to_datetime(sales_long['Datum'], format='%d.%m.%Y', errors='coerce')

# Filter January 2024
jan_sales = sales_long[
    (sales_long['Datum'].dt.year == 2024) &
    (sales_long['Datum'].dt.month == 1)
]
total_revenue = jan_sales['Tržby'].sum()  # e.g., 500_000_000

# PART 3: Calculate ratio
if total_revenue > 0:
    ratio_pct = (abs(rezijni_finance) / total_revenue * 100).round(2)
else:
    ratio_pct = 0.0

# PART 4: Create result
result = pd.DataFrame({{
    'Metrika': ['Režijní náklady Finance', 'Celkový obrat', 'Podíl nákladů na obratu'],
    'Leden 2024': [rezijni_finance, total_revenue, f'{{ratio_pct}}%']
}})
```

**KEY POINTS:**
- Use absolute value for costs (they're negative)
- Check for division by zero
- Format percentage nicely
- Show both components + ratio in result

## 14. INSTRUKCE PRO ODPOVĚĎ:

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
  * "Top 10 dodavatelů v ALZABOX" → title = "Top 10 dodavatelů ALZABOX"
  * "Náklady střediska Finance v Q1" → title = "Náklady Finance Q1"
- Bez zbytečných slov ("Jaké", "Kolik", "Zobraz")
- Český jazyk pokud dotaz byl česky

**Další pravidla:**
1. Vygeneruj POUZE Python kód bez dalšího textu (kromě title)
2. Kód musí být spustitelný bez úprav
3. Nepoužívej markdown code blocks (```)
4. Poslední řádek MUSÍ být: result = [tvůj_dataframe]
5. Pro Sales.csv VŽDY začni UNPIVOT operací
6. VŽDY řaď sestupně (highest first) pokud uživatel neřekne jinak
7. Pro měsíční data VŽDY zahrň YoY % a MoM %

Začni generovat kód NYNÍ (nezapomeň na title na prvním řádku!):"""

    return prompt


def format_data_structure_info(info: dict) -> str:
    """Formátuje informace o struktuře dat."""
    if not info:
        return "Žádná specifická info o struktuře dat."
    
    formatted = []
    for dataset_name, dataset_info in info.items():
        formatted.append(f"\n{dataset_name}:")
        formatted.append(f"  Format: {dataset_info.get('format', 'N/A')}")
        formatted.append(f"  Popis: {dataset_info.get('description', 'N/A')}")
        
        if 'required_transformation' in dataset_info:
            formatted.append(f"  ⚠️ POVINNÁ TRANSFORMACE: {dataset_info['required_transformation']}")
        
        if 'example' in dataset_info:
            formatted.append(f"  Příklad: {dataset_info['example']}")
    
    return "\n".join(formatted)


def format_column_definitions(definitions: dict) -> str:
    """Formátuje definice sloupců."""
    if not definitions:
        return "Žádné specifické definice sloupců."
    
    formatted = []
    for dataset_name, cols in definitions.items():
        formatted.append(f"\n{dataset_name}:")
        for key, value in cols.items():
            formatted.append(f"  - {key}: {value}")
    
    return "\n".join(formatted)


def format_alza_specific_rules(rules: dict) -> str:
    """Formátuje Alza-specifická pravidla."""
    if not rules:
        return "Žádná specifická pravidla."
    
    formatted = []
    for key, value in rules.items():
        if isinstance(value, dict):
            formatted.append(f"\n{key}:")
            for sub_key, sub_value in value.items():
                formatted.append(f"  - {sub_key}: {sub_value}")
        else:
            formatted.append(f"- {key}: {value}")
    
    return "\n".join(formatted)
