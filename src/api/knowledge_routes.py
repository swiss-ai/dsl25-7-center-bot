from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from services.knowledge.document_processor import DocumentProcessor
import logging

# Get the global document_processor from main.py
from main import document_processor

logger = logging.getLogger(__name__)

router = APIRouter()

class DocumentInput(BaseModel):
    """Model for document input."""
    content: str
    title: str
    source: str
    url: Optional[str] = None
    author: Optional[str] = None
    created_at: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

class SearchQuery(BaseModel):
    """Model for search queries."""
    query: str
    limit: int = 5
    filters: Optional[Dict[str, Any]] = None

class SearchResponse(BaseModel):
    """Model for search responses."""
    results: List[Dict[str, Any]]
    count: int
    query: str

@router.post("/documents", response_model=Dict[str, Any])
async def add_document(document: DocumentInput):
    """
    Add a document to the knowledge base.
    """
    if not document_processor:
        raise HTTPException(status_code=503, detail="Document processor not initialized")
    
    try:
        # Prepare metadata
        metadata = document.metadata or {}
        metadata.update({
            "title": document.title,
            "source": document.source,
            "url": document.url,
            "author": document.author,
            "created_at": document.created_at,
            "tags": document.tags or []
        })
        
        # Process the document
        chunk_ids = await document_processor.process_document(
            content=document.content,
            metadata=metadata
        )
        
        return {
            "success": True,
            "document_id": metadata.get("doc_id"),
            "chunks": len(chunk_ids),
            "message": f"Document '{document.title}' added successfully"
        }
    
    except Exception as e:
        logger.error(f"Error adding document: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing document: {str(e)}"
        )

@router.post("/search", response_model=SearchResponse)
async def search_documents(search: SearchQuery):
    """
    Search for documents in the knowledge base.
    """
    if not document_processor:
        raise HTTPException(status_code=503, detail="Document processor not initialized")
    
    try:
        # Perform the search
        results = await document_processor.search_documents(
            query=search.query,
            n_results=search.limit,
            filter_criteria=search.filters
        )
        
        # Format the results
        if not results or not results.get("documents") or not results["documents"][0]:
            return SearchResponse(
                results=[],
                count=0,
                query=search.query
            )
        
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0] if "distances" in results else None
        
        formatted_results = []
        
        for i, (doc, meta) in enumerate(zip(documents, metadatas)):
            formatted_result = {
                "content": doc,
                "metadata": meta,
                "score": distances[i] if distances else None
            }
            formatted_results.append(formatted_result)
        
        return SearchResponse(
            results=formatted_results,
            count=len(formatted_results),
            query=search.query
        )
    
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error searching documents: {str(e)}"
        )

@router.get("/count")
async def get_document_count():
    """
    Get the count of documents in the vector database.
    """
    if not document_processor:
        raise HTTPException(status_code=503, detail="Document processor not initialized")
    
    try:
        count = document_processor.vector_db.count()
        return {"count": count}
    
    except Exception as e:
        logger.error(f"Error getting document count: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting document count: {str(e)}"
        )