"""
Wilco SaaS - Accounting Prompt Module (OPTIMIZED)
Instructions for PL.csv, OVH.csv
"""

ACCOUNTING_INSTRUCTIONS = """
## ACCOUNTING ECOSYSTEM RULES

### DATASETS:
- **PL.csv** = Profit & Loss (výsledovka) - aggregated accounting data
- **OVH.csv** = Overhead expenses (režijní náklady) - detailed document-level data with suppliers

All use WIDE format with monthly columns.

---

### 1. PL.CSV STRUCTURE:
**Key columns:**
- `'Accounting unit name'` - legal entity (Alza.at GmbH, etc.)
- `'CC-Level 1'` - cost center level 1 (ALZABOX, etc.) - **ONLY CC level in PL**
- `'Account class'` - account number (5, 6, etc.)
- `'Analytical account'` - detailed account code (501 200, etc.)
- `'Acc-Level 1'` - account hierarchy level 1 (Režijní náklady, Reklama, etc.)
- `'Acc-Level 2'` - account hierarchy level 2 (Spotreba materialu a Sluzeb, etc.)
- `'Acc-Level 3'` - account hierarchy level 3 (Materiál, Energie, etc.)
- `'Account class - name'` - account class name (Náklady, etc.)
- `'Analytical account - name'` - detailed description (Spotřeba materiálu, etc.)
- Date columns: `'01.01.2024'`, `'01.02.2024'`, etc.

**⚠️ CRITICAL: PL.csv has ONLY CC-Level 1, NOT CC-Level 2!**

```python
pl = PL.copy()

# Filter by cost type (Acc-Level 1):
energy_costs = pl[pl['Acc-Level 1'] == 'Budovy a zařízení']

# Filter by detailed category (Acc-Level 3):
material_costs = pl[pl['Acc-Level 3'] == 'Materiál']

# Filter by cost center (ONLY CC-Level 1 available):
alzabox_costs = pl[pl['CC-Level 1'] == 'ALZABOX']

# ❌ WRONG - CC-Level 2 doesn't exist in PL:
pl[pl['CC-Level 2'] == 'something']  # KeyError!

# Group by hierarchy level:
by_level1 = pl.groupby('Acc-Level 1')[date_cols].sum()
by_level2 = pl.groupby('Acc-Level 2')[date_cols].sum()
by_level3 = pl.groupby('Acc-Level 3')[date_cols].sum()
```

---

### 2. OVH.CSV STRUCTURE (DETAILED DOCUMENTS):
**Key columns:**
- `'Customer/company name'` - **SUPPLIER NAME** (dodavatel)
- `'Accounting unit name'` - legal entity
- `'CC-Level 1'`, `'CC-Level 2'` - cost centers
- `'Analytical account'` - account code
- `'Acc-Level 1'`, `'Acc-Level 2'`, `'Acc-Level 3'` - cost hierarchy
- `'Electronic document key'` - document ID
- `'Document item description'` - item description
- `'Project key'` - project code
- Date columns: `'01.01.2024'`, `'01.02.2024'`, etc.

**CRITICAL: Column name is 'Customer/company name' NOT 'Dodavatel'!**

```python
ovh = OVH.copy()

# ✅ CORRECT - group by supplier:
by_supplier = ovh.groupby('Customer/company name')[date_cols].sum()

# ❌ WRONG - this column doesn't exist:
by_supplier = ovh.groupby('Dodavatel')[date_cols].sum()  # KeyError!
```

---

### 3. COMMON QUERIES:

**TOP suppliers by cost:**
```python
ovh = OVH.copy()
date_cols_2025 = [col for col in ovh.columns if '2025' in col and '.' in col]

# Clean numeric data
for col in date_cols_2025:
    ovh[col] = pd.to_numeric(ovh[col], errors='coerce').fillna(0)

# Group by supplier
by_supplier = ovh.groupby('Customer/company name')[date_cols_2025].sum()
by_supplier['Celkem'] = by_supplier.sum(axis=1)

# Sort ascending (most negative = highest cost)
by_supplier = by_supplier.sort_values('Celkem')

# Take TOP 50
top_50 = by_supplier.head(50)

# Format result
result_data = []
for idx, (supplier, row) in enumerate(top_50.iterrows(), 1):
    result_data.append({
        'Pořadí': idx,
        'Dodavatel': supplier,
        'Náklady (Kč)': f'{abs(row["Celkem"]):,.0f}'.replace(',', ' ')
    })

result = pd.DataFrame(result_data)
```

**Breakdown by cost category:**
```python
pl = PL.copy()
date_cols_2024 = [col for col in pl.columns if '2024' in col and '.' in col]

# Clean numeric data
for col in date_cols_2024:
    pl[col] = pd.to_numeric(pl[col], errors='coerce').fillna(0)

# By Acc-Level 1 (highest level):
by_category = pl.groupby('Acc-Level 1')[date_cols_2024].sum()
by_category['Celkem'] = by_category.sum(axis=1)
by_category = by_category.sort_values('Celkem')  # Ascending (most negative = highest cost)
```

**Režijní náklady (overhead) by department:**
```python
pl = PL.copy()
aug_col = '01.08.2024'

# Clean numeric
pl[aug_col] = pd.to_numeric(pl[aug_col], errors='coerce').fillna(0)

# ✅ CRITICAL: Filter for Režijní náklady ONLY!
pl_rezie = pl[pl['Acc-Level 1'] == 'Režijní náklady']

# Group by department (CC-Level 1)
by_dept = pl_rezie.groupby('CC-Level 1')[aug_col].sum()
by_dept = by_dept.sort_values()  # Most negative first

# Format
result_data = []
for dept, cost in by_dept.items():
    result_data.append({
        'Oddělení': dept,
        'Náklady (Kč)': f'{abs(cost):,.0f}'.replace(',', ' ')
    })
result = pd.DataFrame(result_data)
```

---

### 4. FUZZY MATCHING FOR COSTS:
When user asks for "energie", "mzdy", "marketing", etc.:

```python
# User asks for "energie" (energy):
keyword = 'energie'
energy_rows = pl[
    pl['Acc-Level 3'].str.lower().str.contains(keyword, na=False) |
    pl['Analytical account - name'].str.lower().str.contains(keyword, na=False)
]

# User asks for "materiál" (materials):
keyword = 'materiál'
material_rows = pl[
    pl['Acc-Level 3'].str.lower().str.contains(keyword, na=False) |
    pl['Analytical account - name'].str.lower().str.contains(keyword, na=False)
]
```

---

### 5. COMMON COST TYPES MAPPING:

| User says | Filter in |
|-----------|-----------|
| náklady, costs, expenses | All rows (PL/OVH contain only costs) |
| energie, energy | Acc-Level 3 contains "Energie" |
| materiál, materials | Acc-Level 3 contains "Materiál" |
| mzdy, wages, payroll | Acc-Level 1 contains "Personální" |
| reklama, marketing | Acc-Level 1 contains "Reklama" |
| nájmy, rent | Acc-Level 3 contains "Nájem" |
| opravy, repairs | Acc-Level 3 contains "Opravy" |
| cestovné, travel | Acc-Level 3 contains "Cestovné" |
| dodavatelé, suppliers | Group by 'Customer/company name' in OVH |

---

### 6. PL vs OVH - WHEN TO USE WHICH:

**Use PL.csv when:**
- User asks for aggregated costs (total, by category)
- User asks for "náklady" without mentioning suppliers
- User wants breakdown by Acc-Level hierarchy

**Use OVH.csv when:**
- User asks for "dodavatelé" (suppliers)
- User wants document-level detail
- User asks for specific suppliers by name
- User asks for "TOP dodavatelů"

```python
# User: "Náklady 2024" → Use PL.csv (aggregated)
pl = PL.copy()

# User: "TOP dodavatelé 2024" → Use OVH.csv (has supplier names)
ovh = OVH.copy()
```

---

### 7. YoY COMPARISONS:
```python
jan_2024 = '01.01.2024'
jan_2025 = '01.01.2025'

costs_2024 = pl[jan_2024].sum()
costs_2025 = pl[jan_2025].sum()

yoy_change = ((costs_2025 - costs_2024) / abs(costs_2024) * 100) if costs_2024 != 0 else 0
```

---

### 8. FORMATTING:
- Costs are NEGATIVE values in data
- Display as positive with "Kč" suffix: `f'{abs(value):,.0f}'.replace(',', ' ') + ' Kč'`
- Percentages: always 1 decimal: `f'{pct:.1f}%'`
- Sort costs ascending (most negative first = highest cost)

---

### 9. IMPORTANT NOTES:
- **All values in PL/OVH are NEGATIVE** (accounting convention)
- **Use abs() when displaying** to show as positive amounts
- **Sort ascending** (most negative first) to show highest costs first
- **Clean numeric data** with pd.to_numeric(..., errors='coerce').fillna(0)
- **Supplier column is 'Customer/company name'** NOT 'Dodavatel'!
"""

# Backward compatibility alias
ACCOUNTING_ECOSYSTEM_INSTRUCTIONS = ACCOUNTING_INSTRUCTIONS
