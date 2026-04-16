from playwright.sync_api import sync_playwright
import time
from bs4 import BeautifulSoup
from typing import Optional

BLOCKING_KEYWORDS = ["captcha", "recaptcha", "hcaptcha", "cloudflare", "ray id", "turnstile", "vincit", "px-captcha"]


def check_for_blocks(page) -> tuple[bool, Optional[str]]:
    """
    Busca palabras clave en el contenido de la página que indiquen un bloqueo o CAPTCHA.
    """
    content = page.content().lower()
    for kw in BLOCKING_KEYWORDS:
        if kw in content:
            return True, kw
    return False, None


def scrape_dynamic(url: str, selector: Optional[str] = None) -> dict:
    """
    Realiza scraping de una página dinámica usando Playwright.
    Cambia a modo visible si detecta CAPTCHA o bloqueos.
    Bloquea recursos no necesarios (images, fonts, stylesheets) en modo headless para mayor velocidad.
    """
    with sync_playwright() as p:
        # Iniciamos en headless por defecto
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Bloquear recursos innecesarios en modo headless para acelerar la carga
        def _block_unnecessary_resources(route, request):
            if request.resource_type in ["image", "font", "stylesheet"]:
                route.abort()
            else:
                route.continue_()

        page.route("**/*", _block_unnecessary_resources)

        try:
            # Navegar a la URL con timeout reducido y carga por DOM (más rápido que networkidle)
            page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Verificar si hay bloqueos
            is_blocked, keyword = check_for_blocks(page)

            if is_blocked:
                # Si está bloqueado, cerramos este browser y abrimos uno visible (SIN bloqueo de recursos)
                browser.close()
                browser = p.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()
                page.goto(url)

                # Aquí la app "espera" a que el usuario resuelva el problema
                # Esperaremos a que las palabras clave desaparezcan o pasen 5 minutos
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
                    pass  # Continuamos con lo que haya cargado

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
