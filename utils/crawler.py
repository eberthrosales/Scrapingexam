import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time

def get_base_domain(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"

def build_crawler_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.31",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }

def get_pagination_urls(start_url, max_pages):
    """
    Intenta deducir y recopilar las URLs de las siguientes páginas basándose en el parámetro page o enlaces 'siguiente'.
    Para simplificar, este heurístico busca hrefs en elementos de paginación o con parámetros rel='next'.
    """
    if max_pages <= 1:
        return []

    collected_urls = []
    current_url = start_url
    headers = build_crawler_headers()
    
    for _ in range(max_pages - 1):
        try:
            response = requests.get(current_url, headers=headers, timeout=10)
            if response.status_code != 200:
                break
                
            soup = BeautifulSoup(response.text, "html.parser")
            next_url = None
            
            # 1. Buscar link por rel="next"
            next_link = soup.find("a", rel="next")
            
            # 2. Buscar clases comunes de paginación
            if not next_link:
                paginations = soup.find_all("a", class_=lambda x: x and ('next' in x.lower() or 'siguiente' in x.lower()))
                if paginations:
                    next_link = paginations[0]
                    
            # 3. Buscar título o texto con la flecha o 'siguiente'
            if not next_link:
                for a in soup.find_all("a"):
                    text = a.get_text(strip=True).lower()
                    if text in ['siguiente', 'siguiente »', 'next', 'next »', '>']:
                        next_link = a
                        break
                        
            if next_link and next_link.get("href"):
                next_url = urljoin(start_url, next_link.get("href"))
                
                if next_url in collected_urls or next_url == current_url:
                    break # Evita bucles
                
                collected_urls.append(next_url)
                current_url = next_url
                time.sleep(0.5) # Pausa amigable
            else:
                break # No hay más páginas
                
        except Exception:
            break
            
    return collected_urls

def extract_deep_htmls(base_url, html_content):
    """
    Busca links internos que puedan contener recursos (deep crawl).
    Visita esos links y retorna una lista con todos sus HTML combinados.
    """
    base_domain = get_base_domain(base_url)
    soup = BeautifulSoup(html_content, "html.parser")
    
    internal_links = set()
    
    # Heurísticas de links a investigar: ignoramos navegaciones obvias, login, etc.
    palabras_ignoradas = ['login', 'register', 'contact', 'about', 'terminos', 'privacidad', 'faq', '#']
    
    for a in soup.find_all("a", href=True):
        href = a.get("href")
        full_url = urljoin(base_url, href)
        
        # Debe pertencer al mismo dominio
        if full_url.startswith(base_domain):
            valido = True
            for ign in palabras_ignoradas:
                if ign in full_url.lower() or href.startswith(ign):
                    valido = False
                    break
            
            if valido:
                internal_links.add(full_url)
                
    # Limitar el deep crawl por safety (máximo 50 links internos por página)
    internal_links = list(internal_links)[:50]
    
    deep_html_contents = []
    headers = build_crawler_headers()
    
    for url in internal_links:
        try:
            # Petición super rápida
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                deep_html_contents.append(response.text)
        except:
            pass # Si una falla, no importa, continuamos
            
    return deep_html_contents
