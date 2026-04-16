import io
import zipfile
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Callable


def get_filename_from_url(url: str) -> str:
    """Extrae un posible nombre de archivo de la URL."""
    parsed = urlparse(url)
    filename = parsed.path.split("/")[-1]
    if not filename or filename == '':
        filename = "descarga.bin"
    return filename


def extract_media_links(
    html_content: str,
    base_url: str,
    extract_images: bool = True,
    extract_documents: bool = True
) -> dict[str, set[str]]:
    """
    Busca URLs de imágenes y posibles documentos dentro del HTML.
    Retorna un diccionario de links categorizados.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    links_encontrados: dict[str, set[str]] = {"imagenes": set(), "documentos": set()}

    # Extraer imágenes
    if extract_images:
        for img in soup.find_all("img"):
            src = img.get("src")
            if src and not src.startswith("data:image"):  # Ignorar base64 inlines para descargas
                full_url = urljoin(base_url, src)
                links_encontrados["imagenes"].add(full_url)

    # Extraer documentos (archivos adjuntos o links) genéricos
    if extract_documents:
        # Palabras en el texto del enlace que usualmente denotan una descarga
        descarga_keywords = ['descargar', 'download', 'bajar', 'obtener', 'csv', 'excel', 'adjunto']

        for a in soup.find_all("a"):
            href = a.get("href")
            if href:
                full_url = urljoin(base_url, href)
                # Heurística simple: chequear la extensión
                parsed = urlparse(full_url)
                path = parsed.path.lower()

                texto_enlace = a.get_text(strip=True).lower()

                # Lista de extensiones claras
                if path.endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                                  '.zip', '.rar', '.7z', '.csv', '.txt', '.xml', '.json')):
                    links_encontrados["documentos"].add(full_url)
                # O Atributos HTML claros
                elif "download" in a.attrs or "download" in full_url.lower():
                    links_encontrados["documentos"].add(full_url)
                # O TEXTO Semántico que indica "descargar"
                elif any(kw in texto_enlace for kw in descarga_keywords):
                    # Solo agregar si no parece una simple navegación javascript
                    if not full_url.startswith('javascript:'):
                        links_encontrados["documentos"].add(full_url)

    return links_encontrados


def _download_single_file(url: str, index: int, headers: dict) -> tuple[str, bytes | None]:
    """Descarga un solo archivo desde una URL. Retorna (safe_filename, content) o (safe_filename, None) si falla."""
    safe_filename = f"{index}_{get_filename_from_url(url)}"
    try:
        response = requests.get(url, headers=headers, timeout=15, stream=True)
        if response.status_code == 200:
            # Leer el contenido en trozos para no cargar todo en memoria de golpe
            chunks: list[bytes] = []
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    chunks.append(chunk)
            return safe_filename, b"".join(chunks)
    except Exception as e:
        print(f"Error descargando {url}: {e}")
    return safe_filename, None


def create_zip_from_urls(
    urls: list[str],
    progress_callback: Optional[Callable[[float], None]] = None
) -> bytes:
    """
    Descarga una lista de URLs EN PARALELO usando ThreadPoolExecutor
    y devuelve el contenido de un archivo ZIP en memoria.
    """
    zip_buffer = io.BytesIO()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.31"
    }

    total = len(urls)
    completed = 0

    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        with ThreadPoolExecutor(max_workers=8) as executor:
            # Lanzar todas las descargas en paralelo
            futures = {
                executor.submit(_download_single_file, url, i, headers): i
                for i, url in enumerate(urls)
            }

            for future in as_completed(futures):
                safe_filename, content = future.result()
                if content is not None:
                    zip_file.writestr(safe_filename, content)

                completed += 1
                if progress_callback and total > 0:
                    progress_callback(completed / total)

    return zip_buffer.getvalue()
