"""
Tenant Settings Model
Configurable prompts and settings per tenant
"""

from sqlalchemy import Column, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from app.db.session import Base


class TenantSettings(Base):
    """
    Tenant-specific settings including AI prompts
    
    Each tenant can customize:
    - Company context (who they are, what they do)
    - AI output structure (sections, format)
    - Topic-specific contexts
    """
    
    __tablename__ = "tenant_settings"
    
    # ==========================================
    # COLUMNS
    # ==========================================
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Tenant that owns these settings"
    )
    
    # ==========================================
    # AI PROMPT SETTINGS
    # ==========================================
    
    company_context = Column(
        Text,
        nullable=True,
        comment="Business context about the company (who, what, where)"
    )
    
    output_structure = Column(
        Text,
        nullable=True,
        comment="Desired structure of AI analyst output (markdown template)"
    )
    
    analyst_role = Column(
        Text,
        nullable=True,
        comment="Role description for AI analyst (e.g., 'senior finanční analytik')"
    )
    
    analysis_rules = Column(
        Text,
        nullable=True,
        comment="Rules and guidelines for AI analysis"
    )
    
    topic_contexts = Column(
        JSONB,
        nullable=True,
        comment="Topic-specific contexts: {'payments': '...', 'shipping': '...', ...}"
    )
    
    # ==========================================
    # METADATA
    # ==========================================
    
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    updated_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who last updated settings"
    )
    
    # ==========================================
    # RELATIONSHIPS
    # ==========================================
    
    tenant = relationship(
        "Tenant",
        back_populates="settings"
    )
    
    # ==========================================
    # METHODS
    # ==========================================
    
    def __repr__(self):
        return f"<TenantSettings(tenant_id={self.tenant_id})>"
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "company_context": self.company_context,
            "output_structure": self.output_structure,
            "analyst_role": self.analyst_role,
            "analysis_rules": self.analysis_rules,
            "topic_contexts": self.topic_contexts,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


# ==========================================
# DEFAULT PROMPT VALUES
# ==========================================

DEFAULT_COMPANY_CONTEXT = """- Největší e-commerce v ČR, působí v CZ, SK, HU, AT, DE
- Hlavní segmenty: Telefony, TV/Audio, Počítače, Spotřebiče, Gaming
- AlzaPlus+ = věrnostní program (nižší košík, vyšší frekvence, lepší retence)
- B2B = firemní zákazníci (větší objednávky, nižší marže)
- Sezónnost: Q4 (Black Friday, Vánoce) = peak, Q1 = útlum"""

DEFAULT_ANALYST_ROLE = "Jsi senior finanční analytik (5+ let ve firmě) připravující komentář k datům pro CFO."

DEFAULT_OUTPUT_STRUCTURE = """## 📈 Dynamika dat

Popiš konkrétní trend z dat:
- Růst/pokles z X na Y (absolutní změna)
- Procentuální změna: +/- X%
- Pro více období: YoY, MoM změny
- Pro statická data: rozložení a koncentrace (top 3 tvoří X%)

## 💼 Business zhodnocení

Je tento vývoj POZITIVNÍ nebo NEGATIVNÍ? Proč?
- Implikace pro tržby, marže, náklady
- Dopad na budoucí růst a profitabilitu
- Kontext v rámci strategie firmy

## ⚠️ Rizika

Identifikuj 2-3 hlavní rizika:
- **[Název rizika]**: Popis co hrozí a jak se tomu vyhnout

## 🚀 Příležitosti a doporučení

- Konkrétní příležitosti k růstu
- Actionable doporučení (co udělat)
- Tržní kontext pokud je relevantní"""

DEFAULT_ANALYSIS_RULES = """- Data z tabulky = fakta, MUSÍ být 100% přesná
- Tržní kontext = tvé znalosti, pouze pokud jsi si jistý
- Formát čísel: 1 234 567 Kč, procenta s 1 desetinným (15.3%)
- Piš česky, profesionálně, konkrétně
- NIKDY si nevymýšlej statistiky nebo čísla
- Pokud tržní kontext neznáš, vynech ho"""

DEFAULT_TOPIC_CONTEXTS = {
    "payments": """TRŽNÍ KONTEXT PRO PLATEBNÍ METODY:
Použij své znalosti o trendech v EU e-commerce platbách:
- Podíl karet vs. digitálních peněženek vs. BNPL
- Trendy Apple Pay, Google Pay v CEE regionu
- Preference zákazníků podle segmentů (B2B vs B2C)
DŮLEŽITÉ: Uveď pouze informace, které skutečně znáš.""",
    
    "shipping": """TRŽNÍ KONTEXT PRO DOPRAVU:
Použij své znalosti o last-mile delivery trendech:
- Click & Collect vs. home delivery trendy
- Same-day / next-day delivery v e-commerce
- Výdejní boxy a jejich adopce v CEE
DŮLEŽITÉ: Uveď pouze informace, které skutečně znáš.""",
    
    "segments": """TRŽNÍ KONTEXT PRO PRODUKTOVÉ SEGMENTY:
Použij své znalosti o e-commerce kategoriích:
- Vývoj poptávky po elektronice v EU
- Marže v různých kategoriích
- Sezónnost a trendy
DŮLEŽITÉ: Uveď pouze informace, které skutečně znáš.""",
    
    "customers": """TRŽNÍ KONTEXT PRO ZÁKAZNÍKY:
Použij své znalosti o zákaznických trendech:
- B2B vs B2C chování v e-commerce
- Loyalty programy a jejich efektivita
- Customer retention benchmarky
DŮLEŽITÉ: Uveď pouze informace, které skutečně znáš.""",
    
    "geography": """TRŽNÍ KONTEXT PRO GEOGRAFII:
Použij své znalosti o e-commerce v regionu:
- E-commerce penetrace v jednotlivých zemích CEE
- Růstové trendy podle trhu
- Specifika jednotlivých trhů
DŮLEŽITÉ: Uveď pouze informace, které skutečně znáš.""",
    
    "costs": """TRŽNÍ KONTEXT PRO NÁKLADY A P&L:
Použij své znalosti o nákladových strukturách:
- Typické nákladové poměry v e-commerce/retail
- Energie a materiál jako % tržeb
- Optimalizační příležitosti
DŮLEŽITÉ: Uveď pouze informace, které skutečně znáš.""",
    
    "aov": """TRŽNÍ KONTEXT PRO KOŠÍK/AOV:
Použij své znalosti o e-commerce metrikách:
- Průměrné hodnoty košíku v CEE e-commerce
- Faktory ovlivňující AOV
- Cross-sell a up-sell strategie
DŮLEŽITÉ: Uveď pouze informace, které skutečně znáš.""",
    
    "default": """TRŽNÍ KONTEXT:
Pokud máš relevantní znalosti o tomto tématu z e-commerce nebo retail prostředí, použij je.
DŮLEŽITÉ: Uveď pouze informace, které skutečně znáš. Nevymýšlej konkrétní čísla."""
}
