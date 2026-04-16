import requests
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Optional
import time


def get_base_domain(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def build_crawler_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.31",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }


def get_pagination_urls(start_url: str, max_pages: int) -> list[str]:
    """
    Intenta deducir y recopilar las URLs de las siguientes páginas basándose en el parámetro page o enlaces 'siguiente'.
    Para simplificar, este heurístico busca hrefs en elementos de paginación o con parámetros rel='next'.
    """
    if max_pages <= 1:
        return []

    collected_urls: list[str] = []
    current_url = start_url
    headers = build_crawler_headers()

    for _ in range(max_pages - 1):
        try:
            response = requests.get(current_url, headers=headers, timeout=10)
            if response.status_code != 200:
                break

            soup = BeautifulSoup(response.text, "html.parser")
            next_link = None

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
                    break  # Evita bucles

                collected_urls.append(next_url)
                current_url = next_url
                time.sleep(0.5)  # Pausa amigable
            else:
                break  # No hay más páginas

        except Exception:
            break

    return collected_urls


# ─── Deep Crawl Asíncrono con aiohttp ───────────────────────────────────────

async def _fetch_url(session: aiohttp.ClientSession, url: str, semaphore: asyncio.Semaphore) -> Optional[str]:
    """Descarga una URL de manera asíncrona respetando el semáforo de concurrencia."""
    async with semaphore:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    return await response.text()
        except Exception:
            pass
    return None


async def _async_deep_crawl(urls: list[str], headers: dict[str, str]) -> list[str]:
    """Descarga múltiples URLs en paralelo usando aiohttp y asyncio.gather."""
    semaphore = asyncio.Semaphore(10)
    results: list[str] = []

    async with aiohttp.ClientSession(headers=headers) as session:
        tasks = [_fetch_url(session, url, semaphore) for url in urls]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for resp in responses:
            if isinstance(resp, str):
                results.append(resp)

    return results


def extract_deep_htmls(
    base_url: str,
    html_content: str,
    visited_urls: Optional[set[str]] = None
) -> list[str]:
    """
    Busca links internos que puedan contener recursos (deep crawl).
    Visita esos links de forma asíncrona y retorna una lista con todos sus HTML combinados.
    """
    if visited_urls is None:
        visited_urls = set()

    base_domain = get_base_domain(base_url)
    soup = BeautifulSoup(html_content, "html.parser")

    internal_links: set[str] = set()

    # Heurísticas de links a ignorar
    palabras_ignoradas = ['login', 'register', 'contact', 'about', 'terminos', 'privacidad', 'faq', '#', 'busqueda', 'search']

    for a in soup.find_all("a", href=True):
        href = a.get("href")
        full_url = urljoin(base_url, href)

        # Ignorar si ya lo visitamos
        if full_url in visited_urls:
            continue

        # Debe pertencer al mismo dominio
        if full_url.startswith(base_domain):
            valido = True
            href_lower = href.lower()
            for ign in palabras_ignoradas:
                if ign in full_url.lower() or href_lower.startswith(ign):
                    valido = False
                    break

            if valido:
                internal_links.add(full_url)

    # --- Prioridad Inteligente ---
    # Queremos priorizar links que apunten a datasets o recursos, no páginas variadas
    links_priorizados: list[str] = []
    links_secundarios: list[str] = []

    prioridad_keywords = ['dataset', 'resource', 'recurso', 'download', 'archivo', 'detalle', 'ver', 'datos', 'node']

    for url in internal_links:
        if any(keyword in url.lower() for keyword in prioridad_keywords):
            links_priorizados.append(url)
        else:
            links_secundarios.append(url)

    # Juntar dando prioridad a los buenos
    sorted_links = links_priorizados + links_secundarios

    # Limitar el deep crawl por safety (máximo 50 links internos prioritarios por página)
    sorted_links = sorted_links[:50]

    # Marcar como visitados antes de descargar
    for url in sorted_links:
        visited_urls.add(url)

    # Ejecutar descarga asíncrona
    headers = build_crawler_headers()

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Estamos dentro de un event loop ya corriendo (ej. Jupyter, algún contexto async)
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            result = pool.submit(asyncio.run, _async_deep_crawl(sorted_links, headers)).result()
        return result
    else:
        return asyncio.run(_async_deep_crawl(sorted_links, headers))


# ─── API CKAN Nativa ─────────────────────────────────────────────────────────

def fetch_ckan_datasets(
    base_url: str,
    max_results: int = 100,
    filters: Optional[dict[str, str]] = None
) -> Optional[list[dict]]:
    """
    Detecta si la URL es del dominio datosabiertos.gob.pe y, si es CKAN,
    consulta la API REST para obtener datasets estructurados.

    Retorna una lista de dicts con: title, description, organization,
    date_modified, resources (lista de dicts con url, format, name).
    Si falla la API, retorna None silenciosamente.
    """
    # Solo activar para dominios CKAN conocidos
    if "datosabiertos.gob.pe" not in base_url:
        return None

    api_url = "https://www.datosabiertos.gob.pe/api/3/action/package_search"

    params: dict[str, str | int] = {
        "rows": max_results,
    }

    fq_parts: list[str] = []

    if filters:
        if filters.get("query"):
            params["q"] = filters["query"]
        if filters.get("format"):
            fq_parts.append(f'res_format:"{filters["format"]}"')
        if filters.get("organization"):
            fq_parts.append(f'organization:"{filters["organization"]}"')
        if filters.get("date_from"):
            fq_parts.append(f'metadata_modified:[{filters["date_from"]}T00:00:00Z TO *]')

    if fq_parts:
        params["fq"] = " AND ".join(fq_parts)

    headers = build_crawler_headers()

    try:
        response = requests.get(api_url, params=params, headers=headers, timeout=15)
        if response.status_code != 200:
            return None

        data = response.json()

        if not data.get("success"):
            return None

        results: list[dict] = []
        for pkg in data.get("result", {}).get("results", []):
            org_name = ""
            if pkg.get("organization"):
                org_name = pkg["organization"].get("title", pkg["organization"].get("name", ""))

            resources: list[dict] = []
            for res in pkg.get("resources", []):
                resources.append({
                    "url": res.get("url", ""),
                    "format": res.get("format", ""),
                    "name": res.get("name", res.get("description", "")),
                })

            results.append({
                "title": pkg.get("title", ""),
                "description": pkg.get("notes", ""),
                "organization": org_name,
                "date_modified": pkg.get("metadata_modified", ""),
                "resources": resources,
            })

        return results

    except Exception:
        return None
