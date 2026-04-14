import requests
from bs4 import BeautifulSoup
import re

def detect_page_type(url):
    """
    Intenta detectar si una página es estática o dinámica.
    Retorna 'static', 'dynamic' o 'error'.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.31 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.31"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html = response.text
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Heurísticas para detectar contenido dinámico (SPA, frameworks JS)
        
        # 1. Cuerpo casi vacío (típico de React/Vue/Angular sin SSR)
        body = soup.find("body")
        if body:
            char_count = len(body.get_text(strip=True))
            if char_count < 200:
                # Si hay poco texto pero muchos scripts, es probablemente dinámica
                script_count = len(soup.find_all("script"))
                if script_count > 5:
                    return "dynamic"
        
        # 2. Presencia de etiquetas de carga (placeholder)
        placeholders = ["loading", "cargando", "app-root", "root", "mount"]
        for p in placeholders:
            if soup.find(id=re.compile(p, re.I)) or soup.find(class_=re.compile(p, re.I)):
                # No es definitivo, pero es un fuerte indicador si el char_count es bajo
                pass

        # 3. Detección de bloqueos comunes que requests no puede manejar bien
        if "enable javascript" in html.lower() or "javascript is required" in html.lower():
            return "dynamic"
            
        if "cloudflare" in html.lower() or "ray id" in html.lower():
            return "dynamic"
            
        return "static"
        
    except Exception as e:
        # Si falla el request inicial, intentamos modo dinámico como fallback seguro
        return "dynamic"
