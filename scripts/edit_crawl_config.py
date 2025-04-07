#!/usr/bin/env python3
"""
Script to help manage the Firecrawl configuration file
"""
import os
import sys
import argparse
import yaml
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default configuration file path
DEFAULT_CONFIG_PATH = "crawl_config.yaml"

def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    try:
        if not os.path.exists(config_path):
            logger.warning(f"Configuration file not found: {config_path}")
            
            # Create a default configuration
            config = {
                "global": {
                    "crawl_interval": 24,
                    "max_pages": 100,
                    "include_subdomains": True,
                    "max_depth": 3,
                    "respect_robots_txt": False,
                    "delay": 1.0,
                    "concurrency": 5,
                    "timeout": 30
                },
                "sites": [],
                "exclude_patterns": [
                    "*login*", "*signin*", "*download*", "*.pdf", "*.zip", 
                    "*.exe", "*.dmg", "*private*", "*account*", "*cart*", "*checkout*"
                ]
            }
            
            return config
        
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Ensure required sections exist
        if "global" not in config:
            config["global"] = {}
        if "sites" not in config:
            config["sites"] = []
        if "exclude_patterns" not in config:
            config["exclude_patterns"] = []
        
        return config
        
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        sys.exit(1)

def save_config(config: Dict[str, Any], config_path: str):
    """Save configuration to YAML file."""
    try:
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        
        logger.info(f"Configuration saved to {config_path}")
        
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        sys.exit(1)

def validate_url(url: str) -> bool:
    """Validate URL format."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def list_sites(config: Dict[str, Any]):
    """List all sites in the configuration."""
    sites = config.get("sites", [])
    
    if not sites:
        print("\nNo sites configured for crawling.")
        return
    
    print(f"\nConfigured sites ({len(sites)}):")
    for i, site in enumerate(sites):
        url = site.get("url", "No URL")
        
        # Format parameters if any
        params_str = ""
        if "params" in site:
            params = []
            for k, v in site.get("params", {}).items():
                params.append(f"{k}={v}")
            if params:
                params_str = f" [Params: {', '.join(params)}]"
        
        # Get site-specific overrides
        overrides = []
        for key in site:
            if key not in ["url", "params"] and key in config.get("global", {}):
                overrides.append(f"{key}={site[key]}")
        
        # Format overrides
        overrides_str = f" [Overrides: {', '.join(overrides)}]" if overrides else ""
        
        print(f"{i+1}. {url}{params_str}{overrides_str}")
    
    # Print global settings
    print("\nGlobal settings:")
    for key, value in config.get("global", {}).items():
        print(f"  {key}: {value}")
    
    # Print exclude patterns
    exclude_patterns = config.get("exclude_patterns", [])
    if exclude_patterns:
        print("\nExclude patterns:")
        for i, pattern in enumerate(exclude_patterns):
            print(f"  {i+1}. {pattern}")

def add_site(config: Dict[str, Any], args):
    """Add a new site to the configuration."""
    # Validate URL
    if not args.url:
        logger.error("URL is required")
        return
    
    if not validate_url(args.url):
        logger.error(f"Invalid URL format: {args.url}")
        return
    
    # Check if URL already exists
    urls = [site.get("url") for site in config.get("sites", [])]
    if args.url in urls:
        logger.error(f"URL already exists in configuration: {args.url}")
        return
    
    # Create new site configuration
    new_site = {"url": args.url}
    
    # Add parameters if provided
    if args.params:
        params = {}
        for param in args.params:
            try:
                key, value = param.split("=", 1)
                params[key] = value
            except ValueError:
                logger.warning(f"Invalid parameter format (skipping): {param}")
        if params:
            new_site["params"] = params
    
    # Add max_depth override if provided
    if args.depth is not None:
        new_site["max_depth"] = args.depth
    
    # Add include_subdomains override if provided
    if args.subdomains is not None:
        new_site["include_subdomains"] = args.subdomains
    
    # Add max_pages override if provided
    if args.max_pages is not None:
        new_site["max_pages"] = args.max_pages
    
    # Add interval override if provided
    if args.interval is not None:
        new_site["crawl_interval"] = args.interval
    
    # Add the new site to the configuration
    config["sites"].append(new_site)
    
    logger.info(f"Added site: {args.url}")

def remove_site(config: Dict[str, Any], args):
    """Remove a site from the configuration."""
    if not args.url and args.index is None:
        logger.error("Either URL or index is required")
        return
    
    sites = config.get("sites", [])
    
    if args.index is not None:
        # Remove by index
        try:
            index = int(args.index) - 1  # Convert to 0-based index
            if index < 0 or index >= len(sites):
                logger.error(f"Invalid index: {args.index}")
                return
            
            removed_url = sites[index].get("url", "Unknown")
            sites.pop(index)
            logger.info(f"Removed site at index {args.index}: {removed_url}")
            
        except ValueError:
            logger.error(f"Invalid index format: {args.index}")
            return
    else:
        # Remove by URL
        for i, site in enumerate(sites):
            if site.get("url") == args.url:
                sites.pop(i)
                logger.info(f"Removed site: {args.url}")
                return
        
        logger.error(f"URL not found in configuration: {args.url}")

def update_global(config: Dict[str, Any], args):
    """Update global configuration settings."""
    if not args.setting or "=" not in args.setting:
        logger.error("Invalid setting format. Use key=value")
        return
    
    key, value = args.setting.split("=", 1)
    
    # Try to convert value to appropriate type
    try:
        # Try as int
        if value.isdigit():
            value = int(value)
        # Try as float
        elif "." in value and all(part.isdigit() for part in value.split(".", 1)):
            value = float(value)
        # Try as boolean
        elif value.lower() in ["true", "false"]:
            value = value.lower() == "true"
    except:
        # Keep as string if conversion fails
        pass
    
    # Update global configuration
    config["global"][key] = value
    logger.info(f"Updated global setting: {key}={value}")

def add_exclude(config: Dict[str, Any], args):
    """Add an exclusion pattern."""
    if not args.pattern:
        logger.error("Pattern is required")
        return
    
    exclude_patterns = config.get("exclude_patterns", [])
    
    if args.pattern in exclude_patterns:
        logger.warning(f"Pattern already exists: {args.pattern}")
        return
    
    exclude_patterns.append(args.pattern)
    config["exclude_patterns"] = exclude_patterns
    
    logger.info(f"Added exclusion pattern: {args.pattern}")

def remove_exclude(config: Dict[str, Any], args):
    """Remove an exclusion pattern."""
    if not args.pattern and args.index is None:
        logger.error("Either pattern or index is required")
        return
    
    exclude_patterns = config.get("exclude_patterns", [])
    
    if args.index is not None:
        # Remove by index
        try:
            index = int(args.index) - 1  # Convert to 0-based index
            if index < 0 or index >= len(exclude_patterns):
                logger.error(f"Invalid index: {args.index}")
                return
            
            removed_pattern = exclude_patterns[index]
            exclude_patterns.pop(index)
            logger.info(f"Removed exclusion pattern at index {args.index}: {removed_pattern}")
            
        except ValueError:
            logger.error(f"Invalid index format: {args.index}")
            return
    else:
        # Remove by pattern
        if args.pattern in exclude_patterns:
            exclude_patterns.remove(args.pattern)
            logger.info(f"Removed exclusion pattern: {args.pattern}")
        else:
            logger.error(f"Pattern not found: {args.pattern}")
    
    config["exclude_patterns"] = exclude_patterns

def main():
    parser = argparse.ArgumentParser(description="Manage Firecrawl configuration")
    parser.add_argument("--config", "-c", help=f"Configuration file path (default: {DEFAULT_CONFIG_PATH})",
                       default=DEFAULT_CONFIG_PATH)
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all sites in the configuration")
    
    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new site to the configuration")
    add_parser.add_argument("--url", "-u", required=True, help="URL to crawl")
    add_parser.add_argument("--params", "-p", nargs="+", help="URL parameters in format key=value")
    add_parser.add_argument("--depth", "-d", type=int, help="Maximum crawl depth")
    add_parser.add_argument("--subdomains", "-s", type=lambda x: x.lower() == "true", 
                           help="Include subdomains (true/false)")
    add_parser.add_argument("--max-pages", "-m", type=int, help="Maximum pages to crawl")
    add_parser.add_argument("--interval", "-i", type=int, help="Crawl interval in hours")
    
    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove a site from the configuration")
    remove_parser.add_argument("--url", "-u", help="URL to remove")
    remove_parser.add_argument("--index", "-i", help="Index of the site to remove (1-based)")
    
    # Update global command
    global_parser = subparsers.add_parser("global", help="Update global configuration")
    global_parser.add_argument("--setting", "-s", required=True, help="Setting to update in format key=value")
    
    # Add exclusion pattern command
    exclude_add_parser = subparsers.add_parser("exclude-add", help="Add an exclusion pattern")
    exclude_add_parser.add_argument("--pattern", "-p", required=True, help="Exclusion pattern to add")
    
    # Remove exclusion pattern command
    exclude_remove_parser = subparsers.add_parser("exclude-remove", help="Remove an exclusion pattern")
    exclude_remove_parser.add_argument("--pattern", "-p", help="Exclusion pattern to remove")
    exclude_remove_parser.add_argument("--index", "-i", help="Index of the pattern to remove (1-based)")
    
    args = parser.parse_args()
    
    # Load configuration
    config = load_config(args.config)
    
    # Execute command
    if args.command == "list" or not args.command:
        list_sites(config)
    elif args.command == "add":
        add_site(config, args)
        save_config(config, args.config)
    elif args.command == "remove":
        remove_site(config, args)
        save_config(config, args.config)
    elif args.command == "global":
        update_global(config, args)
        save_config(config, args.config)
    elif args.command == "exclude-add":
        add_exclude(config, args)
        save_config(config, args.config)
    elif args.command == "exclude-remove":
        remove_exclude(config, args)
        save_config(config, args.config)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()