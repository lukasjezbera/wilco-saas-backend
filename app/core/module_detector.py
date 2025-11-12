"""
Module Detector - Auto-detect Business vs Accounting queries
"""

from typing import Literal, Dict, List
import re

ModuleType = Literal['business', 'accounting']


class ModuleDetector:
    """Detekuje jestli user query patří do business nebo accounting modulu"""
    
    # Keywords pro ACCOUNTING (finance, PL, OVH)
    ACCOUNTING_KEYWORDS = [
        # Obecné finance
        'náklad', 'náklady', 'expense', 'expenses', 'cost', 'costs',
        'opex', 'provozní náklady', 'režijní náklady',
        
        # Dodavatelé
        'dodavatel', 'dodavatelé', 'vendor', 'vendors', 'firma',
        'od koho', 'kdo dodává', 'supplier',
        
        # Accounting specifické
        'účet', 'analytical account', 'account class',
        'acc-level', 'účetní', 'accounting',
        
        # Cost centers
        'cost centrum', 'cost center', 'cc-level', 'oddělení', 'tým', 'department',
        
        # Documents/Projects
        'projekt', 'project', 'faktura', 'dokument', 'invoice',
        'eld', 'electronic document',
        
        # P&L specific
        'pl', 'p&l', 'profit', 'loss', 'overhead', 'ovh',
        
        # Kategorie nákladů
        'spotřeba materiálu', 'personální náklady', 'budovy a zařízení',
        'energie', 'telefony', 'cestovné', 'mzdové náklady',
        'external služby', 'opravy', 'nájem',
        
        # Queries
        'kolik jsme zaplatili', 'kolik stojí', 'výdaje', 'úhrady',
        'platba dodavateli', 'invoice', 'bill'
    ]
    
    # Keywords pro BUSINESS (sales, e-commerce)
    BUSINESS_KEYWORDS = [
        # Revenue/Sales
        'tržby', 'tržba', 'revenue', 'sales', 'prodej', 'prodeje',
        'obrat', 'turnover', 'výnosy', 'výnos',  # ← Přidáno výnosy!
        
        # Orders/Documents
        'objednávka', 'objednávky', 'order', 'orders',
        'dokument', 'documents', 'invoice',
        
        # Customers
        'zákazník', 'zákazníci', 'customer', 'customers',
        'b2b', 'b2c', 'business customer',
        
        # Products/Categories
        'produkt', 'produkty', 'product', 'products',
        'kategorie produktu', 'product category',
        'sku', 'zboží',
        
        # Shipping/Payment
        'shipping', 'doprava', 'delivery', 'doručení',
        'payment method', 'platební metoda', 'způsob platby',
        'card', 'cash', 'online banking', 'transfer',
        
        # Margins
        'marže', 'margin', 'zisk', 'profit margin',
        'm3', 'contribution margin',
        
        # Membership
        'alzaplus', 'alza+', 'member', 'membership', 'člen',
        
        # E-commerce specific
        'aov', 'average order value', 'průměrná objednávka',
        'basket', 'košík', 'cart'
    ]
    
    # Datasety jako hint
    DATASET_HINTS = {
        'accounting': ['pl', 'ovh', 'p&l', 'overhead'],
        'business': ['sales', 'documents', 'm3', 'bridge', 'shipping']
    }
    
    def __init__(self):
        """Inicializace detectoru"""
        # Compile regexes for performance
        self.accounting_pattern = re.compile(
            '|'.join(re.escape(kw) for kw in self.ACCOUNTING_KEYWORDS),
            re.IGNORECASE
        )
        self.business_pattern = re.compile(
            '|'.join(re.escape(kw) for kw in self.BUSINESS_KEYWORDS),
            re.IGNORECASE
        )
    
    def detect(self, query: str) -> ModuleType:
        """
        Detekuje modul na základě user query
        
        Args:
            query: User query string
            
        Returns:
            'business' nebo 'accounting'
        """
        query_lower = query.lower()
        
        # Count matches
        accounting_matches = len(self.accounting_pattern.findall(query_lower))
        business_matches = len(self.business_pattern.findall(query_lower))
        
        # Check dataset hints
        for dataset in self.DATASET_HINTS['accounting']:
            if dataset in query_lower:
                accounting_matches += 2  # Extra weight for dataset names
        
        for dataset in self.DATASET_HINTS['business']:
            if dataset in query_lower:
                business_matches += 2
        
        # Decision logic
        if accounting_matches > business_matches:
            return 'accounting'
        elif business_matches > accounting_matches:
            return 'business'
        else:
            # Default: business (je častější)
            return 'business'
    
    def detect_with_confidence(self, query: str) -> Dict[str, any]:
        """
        Detekuje modul + confidence score
        
        Returns:
            {
                'module': 'business' | 'accounting',
                'confidence': float (0-1),
                'accounting_score': int,
                'business_score': int
            }
        """
        query_lower = query.lower()
        
        # Count matches
        accounting_matches = len(self.accounting_pattern.findall(query_lower))
        business_matches = len(self.business_pattern.findall(query_lower))
        
        # Dataset hints
        for dataset in self.DATASET_HINTS['accounting']:
            if dataset in query_lower:
                accounting_matches += 2
        
        for dataset in self.DATASET_HINTS['business']:
            if dataset in query_lower:
                business_matches += 2
        
        # Calculate confidence
        total_matches = accounting_matches + business_matches
        if total_matches == 0:
            # No clear signals - default to business
            return {
                'module': 'business',
                'confidence': 0.5,
                'accounting_score': 0,
                'business_score': 0
            }
        
        # Determine winner
        if accounting_matches > business_matches:
            module = 'accounting'
            confidence = accounting_matches / total_matches
        else:
            module = 'business'
            confidence = business_matches / total_matches if business_matches > 0 else 0.5
        
        return {
            'module': module,
            'confidence': confidence,
            'accounting_score': accounting_matches,
            'business_score': business_matches
        }
    
    def get_suggested_module(self, query: str, available_dataframes: List[str]) -> ModuleType:
        """
        Detekuje modul s ohledem na dostupná data
        
        Args:
            query: User query
            available_dataframes: Seznam načtených dataframes (např. ['PL', 'OVH', 'Sales'])
            
        Returns:
            'business' nebo 'accounting'
        """
        # Základní detekce
        detected = self.detect(query)
        
        # Check if required data available
        available_lower = [df.lower() for df in available_dataframes]
        
        if detected == 'accounting':
            # Accounting needs PL or OVH
            if 'pl' in available_lower or 'ovh' in available_lower:
                return 'accounting'
            else:
                # Fallback to business if accounting data not available
                return 'business'
        
        else:  # business
            # Business needs Sales, Documents, M3, or Bridge
            business_data = ['sales', 'documents', 'm3', 'bridge']
            if any(bd in available_lower for bd in business_data):
                return 'business'
            else:
                # Fallback to accounting if business data not available
                return 'accounting'


# ==========================================
# SINGLETON INSTANCE
# ==========================================

detector = ModuleDetector()


# ==========================================
# CONVENIENCE FUNCTIONS
# ==========================================

def detect_module(query: str) -> ModuleType:
    """Detect module for query"""
    return detector.detect(query)


def detect_with_confidence(query: str) -> Dict:
    """Detect with confidence score"""
    return detector.detect_with_confidence(query)


def get_suggested_module(query: str, available_dataframes: List[str]) -> ModuleType:
    """Detect with data availability check"""
    return detector.get_suggested_module(query, available_dataframes)


# ==========================================
# EXPORT
# ==========================================

__all__ = [
    'ModuleDetector',
    'detector',
    'detect_module',
    'detect_with_confidence',
    'get_suggested_module'
]
