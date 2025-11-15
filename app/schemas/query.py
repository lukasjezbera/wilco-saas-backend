"""
Query schemas for request/response validation
FIXED: result field accepts both List and Dict
ADDED: AI Insights schemas and field in QueryExecuteResponse
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Union, Any
from datetime import datetime


# ==========================================
# 🆕 AI INSIGHTS SCHEMAS
# ==========================================

class AIRecommendation(BaseModel):
    """Single AI-generated business recommendation"""
    title: str
    description: str
    priority: str  # "high" | "medium" | "low"
    effort: str    # "low" | "medium" | "high"


class AIInsights(BaseModel):
    """AI-generated business insights from query results"""
    summary: str
    key_findings: List[str]
    recommendations: List[AIRecommendation]
    risks: List[str]
    opportunities: List[str]
    next_steps: List[str]
    context_notes: Optional[str] = None


# ==========================================
# QUERY REQUEST/RESPONSE SCHEMAS
# ==========================================

class QueryExecuteRequest(BaseModel):
    """Request model for executing a query"""
    query: str = Field(..., description="Natural language query")
    dataset_ids: Optional[List[str]] = Field(None, description="Optional list of dataset IDs to use")
    context: Optional[Dict[str, Any]] = Field(None, description="Optional context from previous query (query, code, result)")


class QueryExecuteResponse(BaseModel):
    """Response model for query execution"""
    query_id: str
    success: bool
    query_text: str
    generated_code: str
    result: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None  # Accepts both List and Dict
    result_rows: Optional[int] = None
    execution_time_ms: int
    error_message: Optional[str] = None
    datasets_used: Optional[List[str]] = None
    ai_insights: Optional[AIInsights] = None  # 🆕 NEW FIELD!

    class Config:
        from_attributes = True


class QueryHistoryItem(BaseModel):
    """Individual query history item"""
    id: str
    query_text: str
    result_rows: Optional[int] = None
    execution_time_ms: int
    success: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class QueryHistoryResponse(BaseModel):
    """Response model for query history"""
    total: int
    items: List[QueryHistoryItem]
