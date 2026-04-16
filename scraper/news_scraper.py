import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
import time

from scraper.detector import detect_page_type
from scraper.static_scraper import scrape_static
from scraper.dynamic_scraper import scrape_dynamic


class NewsScraper:
    """
    Extractor universal de noticias. Funciona con cualquier sitio de noticias
    genérico (BBC, RPP, El Comercio, CNN, etc.) sin selectores hardcodeados.
    """

    ARTICLE_LINK_CLASSES = ['headline', 'title', 'article', 'news', 'nota', 'noticia', 'story',
                            'card', 'entry', 'post', 'item', 'extend-link', 'link']
    ARTICLE_URL_PATTERNS = ['/noticia/', '/articulo/', '/news/', '/article/', '/nota/',
                            '/opinion/', '/politica/', '/economia/', '/sociedad/',
                            '/deportes/', '/mundo/', '/tecnologia/', '/cultura/',
                            '/espectaculos/', '/tendencias/', '/actualidad/']
    YEAR_PATTERN = re.compile(r'/20\d{2}/')
    DATE_PATH_PATTERN = re.compile(r'/\d{4}/\d{2}/\d{2}/')

    DATE_REGEXES = [
        re.compile(r'\d{4}-\d{2}-\d{2}'),                          # 2025-04-15
        re.compile(r'\d{1,2} de \w+ de \d{4}', re.IGNORECASE),     # 15 de abril de 2025
        re.compile(r'\w+ \d{1,2},? \d{4}', re.IGNORECASE),         # April 15, 2025
        re.compile(r'\d{1,2}/\d{1,2}/\d{4}'),                      # 15/04/2025
    ]

    NOISE_CLASSES = ['ad', 'publicidad', 'related', 'recomendado', 'share', 'social',
                     'sidebar', 'widget', 'comment', 'comentario', 'newsletter', 'popup']
    NOISE_TAGS = ['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']

    IMG_IGNORE_KEYWORDS = ['logo', 'icon', 'avatar', 'banner-ad', 'pixel', 'tracker',
                           'sprite', '1x1', 'blank']

    def __init__(self) -> None:
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        }

    # ─── Método Principal ─────────────────────────────────────────────────

    def scrape_news_list(self, url: str, max_articles: int = 50) -> list[dict]:
        """
        Extrae artículos de una sección/listado de noticias.
        Detecta automáticamente si la página es estática o dinámica.
        Si el modo estático no encuentra artículos, reintenta con dinámico.
        """
        base_domain = self._get_base_domain(url)

        # Obtener HTML de la página de listado
        mode = detect_page_type(url)
        if mode == "static":
            result = scrape_static(url)
        else:
            result = scrape_dynamic(url)

        if "error" in result or not result.get("html"):
            return []

        html = result["html"]

        # Encontrar links a artículos individuales
        article_links = self._find_article_links(html, url, base_domain)

        # FALLBACK: Si el modo estático no encontró artículos, reintentar con dinámico
        if not article_links and mode == "static":
            result = scrape_dynamic(url)
            if not result.get("error") and result.get("html"):
                html = result["html"]
                article_links = self._find_article_links(html, url, base_domain)

        # Limitar y deduplicar
        seen: set[str] = set()
        unique_links: list[str] = []
        for link in article_links:
            normalized = link.rstrip("/")
            if normalized not in seen:
                seen.add(normalized)
                unique_links.append(link)
            if len(unique_links) >= max_articles:
                break

        # Extraer cada artículo en paralelo
        articles: list[dict] = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self.scrape_article, link): link
                for link in unique_links
            }
            for future in as_completed(futures):
                try:
                    article = future.result()
                    if article and article.get("titulo"):
                        articles.append(article)
                except Exception:
                    pass

        return articles

    # ─── Extracción de Artículo Individual ────────────────────────────────

    def scrape_article(self, url: str) -> dict:
        """
        Extrae los campos completos de un artículo individual.
        Usa heurísticas universales (sin selectores hardcodeados por dominio).
        """
        article: dict = {
            "titulo": "",
            "fecha": "",
            "autor": "Desconocido",
            "resumen": "",
            "cuerpo": "",
            "imagenes": [],
            "tags_originales": [],
            "url_fuente": url,
            "categoria_ia": "",
        }

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                return article
            html = response.text
        except Exception:
            return article

        soup = BeautifulSoup(html, "html.parser")

        # ── Título ──
        article["titulo"] = self._extract_title(soup)

        # ── Fecha ──
        article["fecha"] = self._extract_date(soup)

        # ── Autor ──
        article["autor"] = self._extract_author(soup)

        # ── Cuerpo y contenedor principal ──
        main_container = self._find_main_container(soup)
        article["cuerpo"] = self._extract_body_text(main_container if main_container else soup)

        # ── Resumen ──
        article["resumen"] = self._extract_summary(soup, article["cuerpo"])

        # ── Imágenes ──
        article["imagenes"] = self._extract_images(main_container if main_container else soup, url)

        # ── Tags ──
        article["tags_originales"] = self._extract_tags(soup)

        # Pequeña pausa para no saturar el servidor
        time.sleep(0.2)

        return article

    # ─── Métodos Privados de Extracción ───────────────────────────────────

    def _extract_title(self, soup: BeautifulSoup) -> str:
        # Prioridad 1: <h1>
        h1 = soup.find("h1")
        if h1 and len(h1.get_text(strip=True)) > 5:
            return h1.get_text(strip=True)
        # Prioridad 2: og:title
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            return og["content"].strip()
        # Prioridad 3: <title>
        title = soup.find("title")
        if title:
            return title.get_text(strip=True)
        return ""

    def _extract_date(self, soup: BeautifulSoup) -> str:
        # Prioridad 1: <time datetime="">
        time_el = soup.find("time", attrs={"datetime": True})
        if time_el:
            return time_el["datetime"]
        # Prioridad 2: article:published_time
        meta_time = soup.find("meta", property="article:published_time")
        if meta_time and meta_time.get("content"):
            return meta_time["content"]
        # Prioridad 3: regex en todo el body text
        body = soup.find("body")
        if body:
            text = body.get_text()
            for pattern in self.DATE_REGEXES:
                match = pattern.search(text)
                if match:
                    return match.group(0)
        return ""

    def _extract_author(self, soup: BeautifulSoup) -> str:
        # Prioridad 1: meta author
        meta = soup.find("meta", attrs={"name": "author"})
        if meta and meta.get("content"):
            return meta["content"].strip()
        # Prioridad 2: [rel="author"]
        rel = soup.find(attrs={"rel": "author"})
        if rel:
            return rel.get_text(strip=True) or "Desconocido"
        # Prioridad 3: clases comunes
        for cls in ['author', 'byline', 'firma', 'periodista', 'autor']:
            el = soup.find(class_=lambda x: x and cls in str(x).lower())
            if el and len(el.get_text(strip=True)) < 100:  # No confundir con párrafos largos
                return el.get_text(strip=True)
        return "Desconocido"

    def _extract_summary(self, soup: BeautifulSoup, body_text: str) -> str:
        # Prioridad 1: meta description
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            return meta["content"].strip()[:500]
        # Prioridad 2: og:description
        og = soup.find("meta", property="og:description")
        if og and og.get("content"):
            return og["content"].strip()[:500]
        # Prioridad 3: primeros 300 chars del cuerpo
        return body_text[:300] if body_text else ""

    def _find_main_container(self, soup: BeautifulSoup) -> Optional[BeautifulSoup]:
        """Encuentra el contenedor principal del artículo."""
        # Prioridad: <article> > [role="main"] > <main> > div con más texto
        article = soup.find("article")
        if article:
            return article

        main_role = soup.find(attrs={"role": "main"})
        if main_role:
            return main_role

        main_tag = soup.find("main")
        if main_tag:
            return main_tag

        # Fallback: el div con mayor cantidad de texto
        best_div = None
        best_len = 0
        for div in soup.find_all("div"):
            text_len = len(div.get_text(strip=True))
            # Evitar el body completo
            if 200 < text_len < 50000 and text_len > best_len:
                best_len = text_len
                best_div = div

        return best_div

    def _extract_body_text(self, container: BeautifulSoup) -> str:
        """Elimina ruido y extrae el texto limpio del contenedor del artículo."""
        # Clonar para no mutar el original
        from copy import copy
        container = copy(container)

        # Eliminar tags de ruido
        for tag_name in self.NOISE_TAGS:
            for tag in container.find_all(tag_name):
                tag.decompose()

        # Eliminar elementos con clases de ruido
        for el in container.find_all(True):
            classes = " ".join(el.get("class", []))
            if any(noise in classes.lower() for noise in self.NOISE_CLASSES):
                el.decompose()

        text = container.get_text(separator="\n")

        # Limpiar líneas vacías excesivas
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)

    def _extract_images(self, container: BeautifulSoup, base_url: str) -> list[str]:
        """Extrae URLs de imágenes relevantes dentro del artículo."""
        images: list[str] = []
        for img in container.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            if not src:
                continue

            # Ignorar imágenes decorativas
            src_lower = src.lower()
            if any(kw in src_lower for kw in self.IMG_IGNORE_KEYWORDS):
                continue
            if src.startswith("data:image"):
                continue

            # Ignorar imágenes pequeñas
            width = img.get("width")
            if width:
                try:
                    if int(str(width).replace("px", "")) < 100:
                        continue
                except ValueError:
                    pass

            full_url = urljoin(base_url, src)
            if full_url not in images:
                images.append(full_url)

        return images

    def _extract_tags(self, soup: BeautifulSoup) -> list[str]:
        """Extrae etiquetas/tags del artículo."""
        tags: list[str] = []

        # Prioridad 1: meta keywords
        meta_kw = soup.find("meta", attrs={"name": "keywords"})
        if meta_kw and meta_kw.get("content"):
            tags.extend([t.strip() for t in meta_kw["content"].split(",") if t.strip()])
            return tags[:20]  # Limitar

        # Prioridad 2: elementos con clases de tags
        for cls in ['tag', 'etiqueta', 'keyword', 'topic', 'tags']:
            elements = soup.find_all(class_=lambda x: x and cls in str(x).lower())
            for el in elements:
                # Tags suelen ser links cortos
                for a in el.find_all("a"):
                    text = a.get_text(strip=True)
                    if text and len(text) < 50 and text not in tags:
                        tags.append(text)

        # Prioridad 3: secciones con "Temas:", "Tags:", "Etiquetas:"
        if not tags:
            for label in ["Temas:", "Tags:", "Etiquetas:", "Temas relacionados:"]:
                el = soup.find(string=re.compile(label, re.IGNORECASE))
                if el and el.parent:
                    container = el.parent.parent if el.parent.name in ["b", "strong", "span"] else el.parent
                    for a in container.find_all("a"):
                        text = a.get_text(strip=True)
                        if text and len(text) < 50 and text not in tags:
                            tags.append(text)

        return tags[:20]

    # ─── Detección de Links a Artículos ───────────────────────────────────

    def _find_article_links(self, html: str, base_url: str, base_domain: str) -> list[str]:
        """
        Detecta links a artículos individuales usando heurísticas universales.
        """
        soup = BeautifulSoup(html, "html.parser")
        scored_links: dict[str, int] = {}

        all_links = soup.find_all("a", href=True)

        for a in all_links:
            href = a.get("href", "")
            full_url = urljoin(base_url, href)

            # Solo links del mismo dominio
            if not full_url.startswith(base_domain):
                continue

            # Ignorar la propia página, anclas, y rutas cortas
            if full_url.rstrip("/") == base_url.rstrip("/"):
                continue
            if href.startswith("#") or href.startswith("javascript:"):
                continue
            path = urlparse(full_url).path
            if len(path) < 5:
                continue

            score = 0

            # Heurística 1: Está dentro de <article>
            if a.find_parent("article"):
                score += 10

            # Heurística 2: Clases del link o su padre/abuelo contienen palabras clave
            link_classes = a.get("class", [])
            parent_classes = a.parent.get("class", []) if a.parent else []
            grandparent_classes = a.parent.parent.get("class", []) if a.parent and a.parent.parent else []
            el_classes = " ".join(link_classes + parent_classes + grandparent_classes)
            if any(cls in el_classes.lower() for cls in self.ARTICLE_LINK_CLASSES):
                score += 8

            # Heurística 3: URL contiene secciones de noticias conocidas
            if any(pattern in full_url.lower() for pattern in self.ARTICLE_URL_PATTERNS):
                score += 4

            # Heurística 4: URL contiene patrón de fecha /YYYY/MM/DD/ (MUY fuerte indicador)
            if self.DATE_PATH_PATTERN.search(full_url):
                score += 10
            elif self.YEAR_PATTERN.search(full_url):
                score += 5

            # Heurística 5: Está dentro de <h1>, <h2> o <h3>
            if a.find_parent("h1") or a.find_parent("h2") or a.find_parent("h3"):
                score += 6

            # Heurística 6: Tiene texto significativo (un titular)
            text = a.get_text(strip=True)
            if len(text) > 20:
                score += 3
            elif len(text) > 10:
                score += 1

            # Heurística 7: URL es larga (los artículos tienen slugs largos)
            if len(path) > 30:
                score += 2

            # Heurística 8: Link tiene atributo title con texto largo
            title_attr = a.get("title", "")
            if len(title_attr) > 15:
                score += 3

            if score >= 2:
                if full_url in scored_links:
                    scored_links[full_url] = max(scored_links[full_url], score)
                else:
                    scored_links[full_url] = score

        # Ordenar por puntaje descendente
        sorted_links = sorted(scored_links.items(), key=lambda x: x[1], reverse=True)
        return [link for link, _ in sorted_links]

    def _get_base_domain(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
