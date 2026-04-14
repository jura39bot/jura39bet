"""
BetIntel Scrapers Package

Modules for scraping football data from various sources.
"""

from .sofascore import SofascoreScraper
from .oddsportal import OddsPortalScraper

__all__ = ['SofascoreScraper', 'OddsPortalScraper']