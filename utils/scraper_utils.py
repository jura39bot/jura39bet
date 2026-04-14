"""
Utilitaires pour les scrapers - anti-détection et gestion des requêtes.
"""

import random
import time
import logging
from typing import Dict, Optional, Callable, Any
from functools import wraps

logger = logging.getLogger(__name__)


# Liste de User-Agents réalistes (dernières versions des navigateurs)
USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Chrome macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    # Firefox macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0",
    # Safari macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    # Edge Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
]


# Headers de base pour simuler un navigateur réel
BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,fr;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


# Cookies de session simulés (à adapter selon les besoins)
DEFAULT_COOKIES = {
    "_ga": "GA1.1.1234567890.1234567890",
    "_gid": "GA1.1.0987654321.0987654321",
}


def get_random_user_agent() -> str:
    """Retourne un User-Agent aléatoire de la liste."""
    return random.choice(USER_AGENTS)


def get_random_headers(referer: Optional[str] = None, extra_headers: Optional[Dict] = None) -> Dict:
    """
    Génère des headers HTTP réalistes et aléatoires.
    
    Args:
        referer: URL de référence (referer)
        extra_headers: Headers supplémentaires à ajouter
        
    Returns:
        Dictionnaire de headers HTTP
    """
    headers = BASE_HEADERS.copy()
    headers["User-Agent"] = get_random_user_agent()
    
    if referer:
        headers["Referer"] = referer
    
    if extra_headers:
        headers.update(extra_headers)
    
    return headers


def simulate_human_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
    """
    Simule un délai humain aléatoire entre les requêtes.
    
    Args:
        min_seconds: Délai minimum en secondes
        max_seconds: Délai maximum en secondes
    """
    delay = random.uniform(min_seconds, max_seconds)
    logger.debug(f"Simulating human delay: {delay:.2f}s")
    time.sleep(delay)


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """
    Décorateur pour retry avec backoff exponentiel.
    
    Args:
        max_retries: Nombre maximum de tentatives
        initial_delay: Délai initial entre les tentatives
        max_delay: Délai maximum entre les tentatives
        exponential_base: Base pour le calcul exponentiel
        exceptions: Tuple d'exceptions à capturer
        
    Returns:
        Décorateur
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries:
                        logger.error(f"Max retries ({max_retries}) reached for {func.__name__}: {e}")
                        raise
                    
                    logger.warning(f"Attempt {attempt}/{max_retries} failed for {func.__name__}: {e}. Retrying in {delay:.2f}s...")
                    time.sleep(delay)
                    delay = min(delay * exponential_base, max_delay)
            
            raise last_exception
        return wrapper
    return decorator


def get_session_cookies(domain: Optional[str] = None) -> Dict:
    """
    Retourne des cookies de session simulés.
    
    Args:
        domain: Domaine pour lequel générer les cookies
        
    Returns:
        Dictionnaire de cookies
    """
    cookies = DEFAULT_COOKIES.copy()
    
    # Ajouter des cookies spécifiques au domaine si nécessaire
    if domain:
        cookies[f"session_{domain.replace('.', '_')}"] = f"sess_{random.randint(1000000000, 9999999999)}"
    
    return cookies


def rotate_proxy(proxies: list) -> Optional[Dict]:
    """
    Sélectionne un proxy aléatoire dans la liste.
    
    Args:
        proxies: Liste de proxies (format: http://user:pass@host:port)
        
    Returns:
        Dictionnaire de configuration proxy ou None
    """
    if not proxies:
        return None
    
    proxy = random.choice(proxies)
    return {
        "http": proxy,
        "https": proxy,
    }


class RequestThrottler:
    """Classe pour gérer le throttling des requêtes."""
    
    def __init__(self, min_delay: float = 1.0, max_delay: float = 3.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.last_request_time = 0
    
    def throttle(self):
        """Attend le temps nécessaire avant la prochaine requête."""
        elapsed = time.time() - self.last_request_time
        delay = random.uniform(self.min_delay, self.max_delay)
        
        if elapsed < delay:
            sleep_time = delay - elapsed
            logger.debug(f"Throttling: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()


def parse_response_status(response) -> Dict:
    """
    Parse la réponse HTTP et retourne des informations utiles.
    
    Args:
        response: Objet réponse requests
        
    Returns:
        Dictionnaire avec les informations de statut
    """
    return {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "url": response.url,
        "is_redirect": response.is_redirect,
        "is_permanent_redirect": response.is_permanent_redirect,
        "history": [r.status_code for r in response.history],
    }
