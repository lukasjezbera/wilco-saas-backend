"""
Query schemas for request/response validation
FIXED: result field accepts both List and Dict
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Union, Any
from datetime import datetime


class QueryExecuteRequest(BaseModel):
    """Request model for executing a query"""
    query: str = Field(..., description="Natural language query")
    dataset_ids: Optional[List[str]] = Field(None, description="Optional list of dataset IDs to use")


class QueryExecuteResponse(BaseModel):
    """Response model for query execution"""
    query_id: str
    success: bool
    query_text: str
    generated_code: str
    result: Optional[Union[List[Dict[str, Any]], Dict[str, Any]]] = None  # ← FIXED: Accepts both List and Dict
    result_rows: Optional[int] = None
    execution_time_ms: int
    error_message: Optional[str] = None
    datasets_used: Optional[List[str]] = None

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
