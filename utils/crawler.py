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


# ─── Scraping Directo del Portal datosabiertos.gob.pe ────────────────────────

def fetch_ckan_datasets(
    base_url: str,
    max_results: int = 100,
    filters: Optional[dict[str, str]] = None
) -> Optional[list[dict]]:
    """
    Extrae datasets del portal datosabiertos.gob.pe mediante scraping directo
    del HTML de búsqueda (Drupal/DKAN). La API CKAN estándar no está disponible
    en este portal.

    Retorna una lista de dicts con: title, description, organization,
    date_modified, resources (lista de dicts con url, format, name).
    Si falla, retorna None silenciosamente.
    """
    # Solo activar para dominios conocidos
    if "datosabiertos.gob.pe" not in base_url:
        return None

    headers = build_crawler_headers()
    search_url = "https://www.datosabiertos.gob.pe/search"

    # Calcular cuántas páginas de búsqueda necesitamos (aprox 10 resultados por página)
    results_per_page = 10
    max_search_pages = min((max_results // results_per_page) + 1, 10)

    all_dataset_links: list[dict] = []

    try:
        for page_num in range(max_search_pages):
            # Construir URL de paginación (Drupal: page=0,0 / page=0,1 / page=0,2 ...)
            params: dict[str, str] = {}
            if page_num > 0:
                params["page"] = f"0,{page_num}"

            # Aplicar filtros si existen
            if filters:
                if filters.get("format"):
                    params["f[0]"] = f'res_format:{filters["format"]}'
                if filters.get("query"):
                    params["query"] = filters["query"]

            response = requests.get(search_url, params=params, headers=headers, timeout=15)
            if response.status_code != 200:
                break

            soup = BeautifulSoup(response.text, "html.parser")

            # Cada resultado está en un div.views-row
            rows = soup.select(".views-row")
            if not rows:
                break

            for row in rows:
                # Título y link al dataset
                title_el = row.select_one("h2 a")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                dataset_path = title_el.get("href", "")
                dataset_url = urljoin("https://www.datosabiertos.gob.pe", dataset_path)

                # Organización
                org_el = row.select_one(".views-field-field-organization")
                organization = ""
                if org_el:
                    organization = org_el.get_text(strip=True)

                # Descripción
                desc_el = row.select_one(".views-field-body .field-content")
                description = ""
                if desc_el:
                    description = desc_el.get_text(strip=True)

                # Formatos disponibles (labels como csv, pdf, xls)
                format_labels = row.select("a.label")
                formats = [lbl.get_text(strip=True).upper() for lbl in format_labels]

                all_dataset_links.append({
                    "title": title,
                    "description": description,
                    "organization": organization,
                    "date_modified": "",
                    "formats_preview": formats,
                    "dataset_url": dataset_url,
                    "resources": [],
                })

            if len(all_dataset_links) >= max_results:
                break

            time.sleep(0.3)  # Pausa cortés

        # Ahora visitamos cada página de dataset para encontrar los links reales de descarga
        for ds in all_dataset_links:
            try:
                resp = requests.get(ds["dataset_url"], headers=headers, timeout=10)
                if resp.status_code != 200:
                    continue

                ds_soup = BeautifulSoup(resp.text, "html.parser")

                # Buscar links de descarga reales en la página del dataset
                # Los recursos suelen estar en links con texto "Descargar" o extensiones de archivo
                resource_links = set()

                for a in ds_soup.find_all("a", href=True):
                    href = a.get("href", "")
                    texto = a.get_text(strip=True).lower()
                    full_url = urljoin(ds["dataset_url"], href)

                    # Detectar por extensión
                    path_lower = urlparse(full_url).path.lower()
                    if path_lower.endswith(('.csv', '.pdf', '.xls', '.xlsx', '.json', '.xml',
                                           '.zip', '.doc', '.docx', '.ppt', '.pptx', '.txt')):
                        resource_links.add(full_url)
                    # O por texto semántico
                    elif any(kw in texto for kw in ['descargar', 'download', 'ver recurso']):
                        if not full_url.startswith('javascript:'):
                            resource_links.add(full_url)
                    # O por atributo download
                    elif "download" in a.attrs:
                        resource_links.add(full_url)

                for r_url in resource_links:
                    fname = r_url.rsplit("/", 1)[-1] if "/" in r_url else "archivo"
                    ext = fname.rsplit(".", 1)[-1].upper() if "." in fname else "DESCONOCIDO"
                    ds["resources"].append({
                        "url": r_url,
                        "format": ext,
                        "name": fname,
                    })

            except Exception:
                continue

        return all_dataset_links if all_dataset_links else None

    except Exception:
        return None

