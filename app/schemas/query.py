"""
Query Schemas
Pydantic models for query execution
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ==========================================
# REQUEST SCHEMAS
# ==========================================

class QueryExecuteRequest(BaseModel):
    """Execute query request"""
    query: str = Field(..., description="Natural language query", min_length=3)
    context_query_id: Optional[str] = Field(None, description="Previous query ID for follow-up")
    dataset_ids: Optional[List[str]] = Field(None, description="Specific datasets to use (optional)")


class AIAnalystRequest(BaseModel):
    """AI Analyst analysis request"""
    query: str = Field(..., description="Analysis request")
    result_data: Dict[str, Any] = Field(..., description="Query result data to analyze")
    format_type: str = Field(default="executive", description="Analysis format: executive, detailed, quick")


# ==========================================
# RESPONSE SCHEMAS
# ==========================================

class QueryExecuteResponse(BaseModel):
    """Query execution response"""
    query_id: str = Field(..., description="Query UUID")
    success: bool = Field(..., description="Query executed successfully")
    query_text: str = Field(..., description="Original query text")
    generated_code: Optional[str] = Field(None, description="Generated Python code")
    result: Optional[Dict[str, Any]] = Field(None, description="Query result as JSON")
    result_rows: Optional[int] = Field(None, description="Number of rows in result")
    execution_time_ms: Optional[int] = Field(None, description="Execution time in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    datasets_used: Optional[List[str]] = Field(None, description="Datasets used in query")


class QueryHistoryItem(BaseModel):
    """Query history item"""
    id: str
    query_text: str
    result_rows: Optional[int]
    execution_time_ms: Optional[int]
    success: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class QueryHistoryResponse(BaseModel):
    """Query history list response"""
    total: int = Field(..., description="Total number of queries")
    items: List[QueryHistoryItem] = Field(..., description="Query history items")


class AIAnalystResponse(BaseModel):
    """AI Analyst analysis response"""
    analysis: str = Field(..., description="AI-generated analysis text")
    format_type: str = Field(..., description="Format used")
    execution_time_ms: int = Field(..., description="Analysis time in milliseconds")
