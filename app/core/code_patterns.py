"""
Univerzální code patterns pro různé typy analýz
Tyto patterns jsou použitelné napříč všemi moduly
"""

# ==========================================
# PATTERN 1: ČASOVÁ ŘADA (MoM % a YoY %)
# ==========================================

PATTERN_TIME_SERIES = """
# ČASOVÁ ŘADA s MoM % a YoY %
# Použití: Pro analýzu vývoje v čase (tržby, náklady, metriky)

# KROK 1: Načti data
df_data = {dataset}.copy()

# KROK 2: Najdi sloupce s datumy (DD.MM.YYYY formát)
date_cols = [col for col in df_data.columns if '.' in str(col) and any(char.isdigit() for char in str(col))]

# KROK 3: Seřaď chronologicky pomocí datetime.datetime.strptime
date_cols_sorted = sorted(date_cols, key=lambda x: datetime.datetime.strptime(x, '%d.%m.%Y'))

# KROK 4: Filtruj období (pokud je specifikováno)
{period_filter}

# KROK 5: Sečti přes všechny řádky pro každý měsíc
monthly_data = []
for col in date_cols_sorted:
    monthly_data.append([col, df_data[col].sum()])

# KROK 6: Vytvoř DataFrame
result = pd.DataFrame(monthly_data, columns=['Měsíc', '{metric_name}'])

# KROK 7: VYPOČÍTEJ MoM % (Month-over-Month růst)
result['{metric_name}_PM'] = result['{metric_name}'].shift(1)
result['MoM %'] = ((result['{metric_name}'] / result['{metric_name}_PM']) - 1) * 100

# KROK 8: VYPOČÍTEJ YoY % (Year-over-Year růst)
result['Month_Num'] = result['Měsíc'].apply(lambda x: datetime.datetime.strptime(x, '%d.%m.%Y').month)
result['Year'] = result['Měsíc'].apply(lambda x: datetime.datetime.strptime(x, '%d.%m.%Y').year)

prev_year_df = result[['Month_Num', 'Year', '{metric_name}']].copy()
prev_year_df['Year'] = prev_year_df['Year'] + 1
prev_year_df = prev_year_df.rename(columns={{'{metric_name}': '{metric_name}_LY'}})

result = result.merge(prev_year_df, on=['Month_Num', 'Year'], how='left')
result['YoY %'] = ((result['{metric_name}'] / result['{metric_name}_LY']) - 1) * 100

# KROK 9: Vymaž pomocné sloupce
result = result[['Měsíc', '{metric_name}', 'MoM %', 'YoY %']]
"""

# ==========================================
# PATTERN 2: ČASOVÁ ŘADA PRO AOV
# ==========================================

PATTERN_TIME_SERIES_AOV = """
# ČASOVÁ ŘADA pro AOV (Average Order Value)
# Speciální pattern pro výpočet poměru dvou datasetů v čase

# KROK 1: Načti data
df_sales = Sales.copy()
df_docs = Documents.copy()

# KROK 2: Najdi sloupce s datumy
date_cols_sales = [col for col in df_sales.columns if '.' in str(col) and any(char.isdigit() for char in str(col))]

# KROK 3: Seřaď chronologicky
date_cols_sorted = sorted(date_cols_sales, key=lambda x: datetime.datetime.strptime(x, '%d.%m.%Y'))

# KROK 4: Filtruj období (pokud je specifikováno)
{period_filter}

# KROK 5: Vypočítej AOV pro každý měsíc
monthly_aov = []
for col in date_cols_sorted:
    sales = df_sales[col].sum()
    docs = df_docs[col].sum()
    aov = sales / docs if docs > 0 else 0
    monthly_aov.append([col, aov])

# KROK 6: Vytvoř DataFrame
result = pd.DataFrame(monthly_aov, columns=['Měsíc', 'AOV (Kč)'])

# KROK 7: VYPOČÍTEJ MoM %
result['AOV_PM'] = result['AOV (Kč)'].shift(1)
result['MoM %'] = ((result['AOV (Kč)'] / result['AOV_PM']) - 1) * 100

# KROK 8: VYPOČÍTEJ YoY %
result['Month_Num'] = result['Měsíc'].apply(lambda x: datetime.datetime.strptime(x, '%d.%m.%Y').month)
result['Year'] = result['Měsíc'].apply(lambda x: datetime.datetime.strptime(x, '%d.%m.%Y').year)

prev_year_df = result[['Month_Num', 'Year', 'AOV (Kč)']].copy()
prev_year_df['Year'] = prev_year_df['Year'] + 1
prev_year_df = prev_year_df.rename(columns={{'AOV (Kč)': 'AOV_LY'}})

result = result.merge(prev_year_df, on=['Month_Num', 'Year'], how='left')
result['YoY %'] = ((result['AOV (Kč)'] / result['AOV_LY']) - 1) * 100

# KROK 9: Vymaž pomocné sloupce
result = result[['Měsíc', 'AOV (Kč)', 'MoM %', 'YoY %']]
"""

# ==========================================
# PATTERN 3: BREAKDOWN (podle dimenze)
# ==========================================

PATTERN_BREAKDOWN = """
# BREAKDOWN podle dimenze s procentním podílem

# KROK 1: Načti data
df_data = {dataset}.copy()

# KROK 2: Najdi sloupec pro období
{period_column_search}

# KROK 3: Najdi sloupec pro dimenzi
{dimension_column_search}

# KROK 4: Aplikuj filtry (pokud jsou)
{filters}

# KROK 5: Seskup podle dimenze a sečti hodnoty
result = df_data.groupby({dimension_col})[{period_col}].sum().reset_index()
result.columns = ['{dimension_name}', '{metric_name}']
result = result.sort_values('{metric_name}', ascending=False)

# KROK 6: Vypočítej procentní podíl
result['Podíl %'] = (result['{metric_name}'] / result['{metric_name}'].sum()) * 100

# KROK 7: Přidej řádek CELKEM
total_row = pd.DataFrame([['{celkem_label}', result['{metric_name}'].sum(), 100.0]], 
                        columns=result.columns)
result = pd.concat([result, total_row], ignore_index=True)
"""

# ==========================================
# PATTERN 4: POMĚR/PODÍL
# ==========================================

PATTERN_RATIO = """
# POMĚR/PODÍL s transparentním výpočtem (čitatel, jmenovatel, výsledek)

# KROK 1: Načti data
{data_loading}

# KROK 2: Najdi sloupec pro období
{period_column_search}

# KROK 3: Vypočítej čitatel
{numerator_calculation}

# KROK 4: Vypočítej jmenovatel
{denominator_calculation}

# KROK 5: Vypočítej poměr
{ratio_calculation}

# KROK 6: Vytvoř DataFrame s transparentním výpočtem
result = pd.DataFrame({{
    'Metrika': ['{numerator_label}', '{denominator_label}', '{ratio_label}'],
    'Hodnota': [{numerator_var}, {denominator_var}, {ratio_var}],
    'Jednotka': ['{numerator_unit}', '{denominator_unit}', '{ratio_unit}']
}})
"""

# ==========================================
# PATTERN 5: SOUČET S FILTREM
# ==========================================

PATTERN_SUM_WITH_FILTER = """
# CELKOVÝ SOUČET s aplikovaným filtrem

# KROK 1: Načti data
df_data = {dataset}.copy()

# KROK 2: Najdi sloupec pro období
{period_column_search}

# KROK 3: Najdi sloupec pro filtr
{filter_column_search}

# KROK 4: Aplikuj filtr
{filter_logic}

# KROK 5: Sečti celkové hodnoty pro dané období
result = df_data[{period_col}].sum()
"""

# ==========================================
# HELPER: Hledání sloupců
# ==========================================

COLUMN_SEARCH_PATTERN = """
# Najdi sloupec pro {description}
{var_name} = None
for col in {dataframe}.columns:
    col_str = str(col).lower()
    if {conditions}:
        {var_name} = col
        break
"""

# ==========================================
# HELPER: Filtrování období
# ==========================================

PERIOD_FILTER_PATTERN = """
# Filtruj pouze měsíce od {start_date}
filtered_cols = []
for col in date_cols_sorted:
    col_date = datetime.datetime.strptime(col, '%d.%m.%Y')
    if col_date >= datetime.datetime({year}, {month}, 1):
        filtered_cols.append(col)

if len(filtered_cols) > 0:
    date_cols_sorted = filtered_cols
"""

# ==========================================
# HELPER: B2B filtr
# ==========================================

FILTER_B2B = """
# B2B filtr
b2b_col = None
for col in df_data.columns:
    col_str = str(col).lower()
    if 'customer' in col_str and 'business' in col_str:
        b2b_col = col
        break

if b2b_col is not None:
    df_data = df_data[~df_data[b2b_col].str.contains('not', case=False, na=False)]
    print(f'✓ Filtrováno pouze B2B zákazníci: {{len(df_data):,}} řádků')
"""

# ==========================================
# HELPER: AlzaPlus filtr
# ==========================================

FILTER_ALZAPLUS = """
# AlzaPlus filtr
alzaplus_col = None
for col in df_data.columns:
    col_str = str(col).lower()
    if 'alza' in col_str and 'plus' in col_str:
        alzaplus_col = col
        break

if alzaplus_col is not None:
    df_data = df_data[df_data[alzaplus_col] == 'AlzaPlus+']
    print(f'✓ Filtrováno pouze AlzaPlus+ členové: {{len(df_data):,}} řádků')
"""