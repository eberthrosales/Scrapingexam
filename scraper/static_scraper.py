import requests
from bs4 import BeautifulSoup

def scrape_static(url, selector=None):
    """
    Realiza scraping de una página estática usando requests y BeautifulSoup.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.31 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.31"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        html = response.text
        
        soup = BeautifulSoup(html, "html.parser")
        
        if selector:
            elements = soup.select(selector)
            if not elements:
                return {"error": f"No se encontraron elementos con el selector: {selector}", "html": html}
            
            results = []
            for el in elements:
                results.append({
                    "tag": el.name,
                    "text": el.get_text(strip=True),
                    "html": str(el)
                })
            return {"data": results, "type": "structured", "html": html}
        
        return {"data": html, "type": "raw", "html": html}
        
    except Exception as e:
        return {"error": str(e)}
