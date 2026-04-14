from playwright.sync_api import sync_playwright
import time
from bs4 import BeautifulSoup

BLOCKING_KEYWORDS = ["captcha", "recaptcha", "hcaptcha", "cloudflare", "ray id", "turnstile", "vincit", "px-captcha"]

def check_for_blocks(page):
    """
    Busca palabras clave en el contenido de la página que indiquen un bloqueo o CAPTCHA.
    """
    content = page.content().lower()
    for kw in BLOCKING_KEYWORDS:
        if kw in content:
            return True, kw
    return False, None

def scrape_dynamic(url, selector=None):
    """
    Realiza scraping de una página dinámica usando Playwright.
    Cambia a modo visible si detecta CAPTCHA o bloqueos.
    """
    with sync_playwright() as p:
        # Iniciamos en headless por defecto
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            # Navegar a la URL
            page.goto(url, wait_until="networkidle", timeout=60000)
            
            # Verificar si hay bloqueos
            is_blocked, keyword = check_for_blocks(page)
            
            if is_blocked:
                # Si está bloqueado, cerramos este browser y abrimos uno visible
                browser.close()
                browser = p.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()
                page.goto(url)
                
                # Aquí la app "espera" a que el usuario resuelva el problema
                # En un entorno real de Streamlit, podríamos necesitar una señal manual
                # pero para esta versión, esperaremos a que las palabras clave desaparezcan
                # o pasen 5 minutos
                start_time = time.time()
                while is_blocked and (time.time() - start_time < 300):
                    time.sleep(2)
                    is_blocked, _ = check_for_blocks(page)
                
                # Esperar a que cargue el contenido después del CAPTCHA
                page.wait_for_load_state("networkidle")

            # Si se proporcionó un selector, esperamos a que aparezca
            if selector:
                try:
                    page.wait_for_selector(selector, timeout=10000)
                except:
                    pass # Continuamos con lo que haya cargado
            
            html = page.content()
            
            if selector:
                soup = BeautifulSoup(html, "html.parser")
                elements = soup.select(selector)
                if not elements:
                    return {"error": f"No se encontraron elementos con el selector: {selector} tras renderizado JS.", "html": html}
                
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
            return {"error": f"Error en Playwright: {str(e)}"}
        finally:
            browser.close()
