from typing import List, Dict, Any, Optional
from src.knowledge_sources.notion.connector import NotionConnector
from src.knowledge_sources.airtable.connector import AirtableConnector
from src.knowledge_sources.web_scraper.connector import WebScraperConnector
from src.knowledge_sources.google_drive.connector import GoogleDriveConnector
from src.knowledge_sources.email.connector import EmailConnector
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class KnowledgeRetriever:
    """Unified interface for retrieving knowledge from various sources"""
    
    def __init__(self):
        # Initialize connectors
        self.notion_connector = NotionConnector()
        self.airtable_connector = AirtableConnector()
        self.web_scraper_connector = WebScraperConnector()
        self.google_drive_connector = GoogleDriveConnector()
        self.email_connector = EmailConnector()
        logger.info("Knowledge retriever initialized")
    
    def search(self, query: str, sources: List[str] = None, n_results: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search across multiple knowledge sources
        
        Args:
            query: Search query
            sources: List of sources to search (None = all available)
            n_results: Number of results per source
            
        Returns:
            Dictionary mapping source names to their results
        """
        if sources is None:
            sources = ["notion", "airtable", "web_content", "google_drive", "email"]  # Add more as implemented
        
        results = {}
        
        # Search Notion
        if "notion" in sources:
            try:
                notion_results = self.notion_connector.search(query, n_results)
                results["notion"] = notion_results
                logger.debug(f"Found {len(notion_results)} results from Notion")
            except Exception as e:
                logger.error(f"Error searching Notion: {e}")
                results["notion"] = []
        
        # Search Airtable (both cached and direct with deduplication)
        if "airtable" in sources:
            try:
                # Get both cached and direct results with deduplication
                cached_results, direct_results = self.airtable_connector.search_with_deduplication(query, n_results)
                
                # Combine results, prioritizing non-duplicate direct results
                combined_results = []
                
                # First add non-duplicate direct results (most up-to-date)
                for result in direct_results:
                    if not result["metadata"].get("is_duplicate", False):
                        combined_results.append(result)
                
                # Then add cached results up to n_results
                for result in cached_results:
                    if len(combined_results) < n_results:
                        combined_results.append(result)
                
                results["airtable"] = combined_results[:n_results]
                
                # Log statistics
                duplicate_count = sum(1 for r in direct_results if r["metadata"].get("is_duplicate", False))
                logger.debug(f"Airtable search: {len(cached_results)} cached, {len(direct_results)} direct ({duplicate_count} duplicates)")
                
            except Exception as e:
                logger.error(f"Error searching Airtable: {e}")
                results["airtable"] = []
        
        # Search Web Content
        if "web_content" in sources:
            try:
                web_results = self.web_scraper_connector.search(query, n_results)
                results["web_content"] = web_results
                logger.debug(f"Found {len(web_results)} results from Web Content")
            except Exception as e:
                logger.error(f"Error searching Web Content: {e}")
                results["web_content"] = []
        
        # Search Google Drive
        if "google_drive" in sources:
            try:
                google_drive_results = self.google_drive_connector.search(query, n_results)
                results["google_drive"] = google_drive_results
                logger.debug(f"Found {len(google_drive_results)} results from Google Drive")
            except Exception as e:
                logger.error(f"Error searching Google Drive: {e}")
                results["google_drive"] = []
        
        # Search Email
        if "email" in sources:
            try:
                email_results = self.email_connector.search(query, n_results)
                results["email"] = email_results
                logger.debug(f"Found {len(email_results)} results from Email")
            except Exception as e:
                logger.error(f"Error searching Email: {e}")
                results["email"] = []
        
        return results
    
    def format_search_results_for_context(self, results: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Format search results as context for Claude
        
        Args:
            results: Dictionary of search results by source
            
        Returns:
            Formatted string context
        """
        if not any(results.values()):
            return ""
        
        context_parts = ["Relevant information from knowledge base:"]
        
        for source, source_results in results.items():
            if not source_results:
                continue
                
            context_parts.append(f"\n--- From {source.title()} ---")
            
            for i, result in enumerate(source_results[:3]):  # Limit to top 3 per source
                metadata = result.get("metadata", {})
                content = result.get("content", "")
                
                # Add source citation
                citation_parts = []
                
                # Notion-specific metadata
                if metadata.get("page_title"):
                    citation_parts.append(f"Page: {metadata['page_title']}")
                if metadata.get("notion_url"):
                    citation_parts.append(f"URL: {metadata['notion_url']}")
                
                # Airtable-specific metadata
                if metadata.get("table_name"):
                    citation_parts.append(f"Table: {metadata['table_name']}")
                if metadata.get("record_id"):
                    citation_parts.append(f"Record: {metadata['record_id']}")
                if metadata.get("airtable_url"):
                    citation_parts.append(f"URL: {metadata['airtable_url']}")
                elif metadata.get("base_url"):
                    citation_parts.append(f"Base URL: {metadata['base_url']}")
                
                # Web Content-specific metadata
                if metadata.get("web_url"):
                    citation_parts.append(f"URL: {metadata['web_url']}")
                elif metadata.get("url"):
                    citation_parts.append(f"URL: {metadata['url']}")
                if metadata.get("title"):
                    citation_parts.append(f"Title: {metadata['title']}")
                
                # Google Drive-specific metadata
                if metadata.get("file_name"):
                    citation_parts.append(f"File: {metadata['file_name']}")
                if metadata.get("google_drive_url"):
                    citation_parts.append(f"URL: {metadata['google_drive_url']}")
                if metadata.get("file_type"):
                    citation_parts.append(f"Type: {metadata['file_type']}")
                
                # Email-specific metadata
                if metadata.get("subject"):
                    citation_parts.append(f"Subject: {metadata['subject']}")
                if metadata.get("from"):
                    citation_parts.append(f"From: {metadata['from']}")
                if metadata.get("date"):
                    citation_parts.append(f"Date: {metadata['date']}")
                if metadata.get("gmail_url"):
                    citation_parts.append(f"URL: {metadata['gmail_url']}")
                
                # Add search type indicator for Airtable
                if metadata.get("search_type") == "direct":
                    citation_parts.append("(Live Data)")
                elif metadata.get("source_type") == "airtable":
                    citation_parts.append("(Cached)")
                
                citation = " | ".join(citation_parts) if citation_parts else "No citation available"
                
                context_parts.append(f"\n[{i+1}] {citation}")
                context_parts.append(f"{content[:500]}...")  # Limit content length
        
        return "\n".join(context_parts)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics from all knowledge sources"""
        stats = {
            "sources": {}
        }
        
        # Get Notion stats
        try:
            stats["sources"]["notion"] = self.notion_connector.get_stats()
        except Exception as e:
            logger.error(f"Error getting Notion stats: {e}")
            stats["sources"]["notion"] = {"error": str(e)}
        
        # Get Airtable stats
        try:
            stats["sources"]["airtable"] = self.airtable_connector.get_stats()
        except Exception as e:
            logger.error(f"Error getting Airtable stats: {e}")
            stats["sources"]["airtable"] = {"error": str(e)}
        
        # Get Web Content stats
        try:
            stats["sources"]["web_content"] = self.web_scraper_connector.get_stats()
        except Exception as e:
            logger.error(f"Error getting Web Content stats: {e}")
            stats["sources"]["web_content"] = {"error": str(e)}
        
        # Get Google Drive stats
        try:
            stats["sources"]["google_drive"] = self.google_drive_connector.get_stats()
        except Exception as e:
            logger.error(f"Error getting Google Drive stats: {e}")
            stats["sources"]["google_drive"] = {"error": str(e)}
        
        # Get Email stats
        try:
            stats["sources"]["email"] = self.email_connector.get_stats()
        except Exception as e:
            logger.error(f"Error getting Email stats: {e}")
            stats["sources"]["email"] = {"error": str(e)}
        
        return stats