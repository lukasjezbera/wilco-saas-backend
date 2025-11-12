"""
Alza - Business Configuration
Konfigurace specifická pro Alza business data
"""

from modules.business import config as business_module

# ==========================================
# IMPORT Z BUSINESS MODULU
# ==========================================

# Použij business module jako základ
DATASETS_DESCRIPTION = business_module.DATASETS_DESCRIPTION
CATEGORY_DEFINITIONS = business_module.CATEGORY_DEFINITIONS
COLUMN_SEARCH_EXAMPLES = business_module.COLUMN_SEARCH_EXAMPLES
DATASETS = business_module.DATASETS
METRICS = business_module.METRICS
BUSINESS_RULES = business_module.BUSINESS_RULES
DIMENSIONS = business_module.DIMENSIONS

# ==========================================
# REQUIRED FILES
# ==========================================

REQUIRED_FILES = {
    'Sales': 'Sales.csv',
    'Documents': 'Documents.csv',
    'M3': 'M3.csv',
    'Bridge': 'Bridge_Shipping_Types.csv'
}

# ==========================================
# ALZA-SPECIFICKÉ NASTAVENÍ
# ==========================================

COMPANY_NAME = "Alza"
MODULE_TYPE = "business"

# Cesty k datům (relativní k Data/)
DATA_FOLDER = "Data"

# Enkódování souborů
ENCODING_PRIORITY = [
    {"encoding": "utf-8", "sep": ";", "decimal": ","},
    {"encoding": "utf-8", "sep": ",", "decimal": "."},
    {"encoding": "utf-8", "sep": ";"},
    {"encoding": "latin1", "sep": ";", "decimal": ","},
    {"encoding": "latin1", "sep": ","}
]

# ==========================================
# DATA STRUCTURE INFORMATION
# ==========================================

DATA_STRUCTURE_INFO = {
    "Sales.csv": {
        "format": "wide_pivoted",
        "description": "Data jsou v WIDE formátu - datumy jsou sloupce (01.01.2024, 01.02.2024, ...)",
        "date_columns": "Všechny sloupce ve formátu DD.MM.YYYY (např. 01.01.2024, 01.02.2024)",
        "dimension_columns": [
            "AlzaPlus+",
            "Eshop site country", 
            "Customer is business customer (IN/TIN)",
            "Payment detail name",
            "Shipping group",
            "Shipping name",
            "Shipping detail name",
            "Source platform",
            "Sourcing",
            "Catalogue segment 1"
        ],
        "value_meaning": "Hodnoty v datumových sloupcích = tržby v Kč bez DPH",
        "required_transformation": "UNPIVOT (melt) - převést široký formát na dlouhý",
        "example": """
        PŘED (WIDE):
        Platební metoda | 01.01.2024 | 01.02.2024
        eBanka         | 123456     | 234567
        
        PO UNPIVOT (LONG):
        Platební metoda | Datum      | Tržby
        eBanka         | 01.01.2024 | 123456
        eBanka         | 01.02.2024 | 234567
        """
    },
    "Documents.csv": {
        "format": "long",
        "description": "Klasický long formát - každý řádek = jedna transakce"
    },
    "M3.csv": {
        "format": "mixed",
        "description": "Kombinace dimenzí a časových sloupců"
    }
}

# ==========================================
# COLUMN DEFINITIONS
# ==========================================

COLUMN_DEFINITIONS = {
    "Sales.csv": {
        "revenue_columns": "Všechny sloupce s datem (DD.MM.YYYY formát)",
        "date_format": "DD.MM.YYYY",
        "payment_method": "Payment detail name",
        "shipping_method": "Shipping name",
        "customer_type": "Customer is business customer (IN/TIN)",
        "alzaplus": "AlzaPlus+",
        "country": "Eshop site country"
    }
}

# ==========================================
# ALZA BUSINESS RULES (rozšíření)
# ==========================================

ALZA_SPECIFIC_RULES = {
    "B2B_exact_values": {
        "b2b": "Customer is business customer (IN/TIN)",
        "b2c": "Customer is not business customer (IN/TIN)"
    },
    "AlzaPlus_exact_values": {
        "member": "AlzaPlus+",
        "non_member": "Customer is not member of AlzaPlus+ program"
    },
    "shipping_rules": {
        "primary_grouping_column": "ShippingType",
        "dataset": "Bridge_Shipping_Types.csv",
        "description_columns": ["Shipping name", "Shipping detail name"],
        "rule": "ALWAYS group by ShippingType. Shipping name and Shipping detail name are ONLY for labels/descriptions, NEVER for grouping!",
        "user_queries_keywords": ["metody doručení", "doprava", "distribuce", "shipping", "delivery", "doručení"]
    },
    "encoding": "UTF-8 required for Czech characters"
}

# ==========================================
# CONFIG METADATA
# ==========================================

CONFIG_INFO = {
    "company": COMPANY_NAME,
    "module": MODULE_TYPE,
    "version": "1.1",
    "created": "2024-11-08",
    "updated": "2024-11-09",
    "description": "Konfigurace pro Alza business analytics s podporou WIDE format dat"
}

# ==========================================
# HELPER FUNKCE
# ==========================================

def get_full_config():
    """Vrátí kompletní konfiguraci pro tento modul"""
    return {
        "REQUIRED_FILES": REQUIRED_FILES,
        "DATASETS_DESCRIPTION": DATASETS_DESCRIPTION,
        "CATEGORY_DEFINITIONS": CATEGORY_DEFINITIONS,
        "COLUMN_SEARCH_EXAMPLES": COLUMN_SEARCH_EXAMPLES,
        "DATASETS": DATASETS,
        "METRICS": METRICS,
        "BUSINESS_RULES": BUSINESS_RULES,
        "DIMENSIONS": DIMENSIONS,
        "COMPANY_NAME": COMPANY_NAME,
        "MODULE_TYPE": MODULE_TYPE,
        "CONFIG_INFO": CONFIG_INFO,
        "DATA_STRUCTURE_INFO": DATA_STRUCTURE_INFO,
        "COLUMN_DEFINITIONS": COLUMN_DEFINITIONS,
        "ALZA_SPECIFIC_RULES": ALZA_SPECIFIC_RULES
    }
