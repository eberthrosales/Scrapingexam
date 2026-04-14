import io
import zipfile
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import mimetypes

def get_filename_from_url(url):
    """Extrae un posible nombre de archivo de la URL."""
    parsed = urlparse(url)
    filename = parsed.path.split("/")[-1]
    if not filename or filename == '':
        filename = "descarga.bin"
    return filename

def extract_media_links(html_content, base_url, extract_images=True, extract_documents=True):
    """
    Busca URLs de imágenes y posibles documentos dentro del HTML.
    Retorna un diccionario de links categorizados.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    links_encontrados = {"imagenes": set(), "documentos": set()}
    
    # Extraer imágenes
    if extract_images:
        for img in soup.find_all("img"):
            src = img.get("src")
            if src and not src.startswith("data:image"): # Ignorar base64 inlines para descargas
                full_url = urljoin(base_url, src)
                links_encontrados["imagenes"].add(full_url)
                
    # Extraer documentos (archivos adjuntos o links) genéricos
    if extract_documents:
        for a in soup.find_all("a"):
            href = a.get("href")
            if href:
                full_url = urljoin(base_url, href)
                # Heurística simple: chequear la extensión
                parsed = urlparse(full_url)
                path = parsed.path.lower()
                
                # Lista común de documentos o asume todo si el user lo requiere, pero aquí limitamos
                # a cosas que parecen documentos descargables, aunque el usuario pidio 'todos los archivos' 
                # descargaremos los links que no parezcan simples rutas de navegación
                if path.endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', 
                                  '.zip', '.rar', '.7z', '.csv', '.txt', '.xml', '.json')):
                    links_encontrados["documentos"].add(full_url)
                elif "download" in a.attrs or "download" in full_url.lower():
                    # Si tiene el atributo de descarga o la palabra download, lo incluimos
                    links_encontrados["documentos"].add(full_url)
                    
    return links_encontrados

def create_zip_from_urls(urls):
    """
    Descarga una lista de URLs y devuelve el contenido de un archivo ZIP en memoria.
    """
    zip_buffer = io.BytesIO()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.31"
    }

    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        for i, url in enumerate(urls):
            try:
                response = requests.get(url, headers=headers, timeout=10, stream=True)
                if response.status_code == 200:
                    filename = get_filename_from_url(url)
                    
                    # Agregar un prefijo para evitar sobreescribir archivos con el mismo nombre
                    safe_filename = f"{i}_{filename}"
                    
                    zip_file.writestr(safe_filename, response.content)
            except Exception as e:
                # Si falla la descarga de uno, simplemente continuamos con el siguiente
                print(f"Error descargando {url}: {e}")
                
    return zip_buffer.getvalue()
