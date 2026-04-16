# Scraper Dinámico Universal 🕸️

Una herramienta de extracción de datos potente, modular y versátil construida con **Python** y **Streamlit**. Extrae texto, imágenes, documentos, conjuntos de datos (datasets) y noticias categorizadas de cualquier sitio web, incluyendo portales gubernamentales con paginación compleja o renderizado del lado del cliente (SPA).

## 🚀 Características Principales

### 1. Scraper General y Descarga Multimedia
- 🤖 **Detección Automática:** Identifica si la página es estática (HTML puro) o dinámica (JS/React/Angular) para alternar entre `requests` y `Playwright` sin fricción.
- 🖼️ **Extracción Multimedia:** Obtiene imágenes y documentos (PDF, CSV, XLS, ZIP, etc.), consolidando todos los enlaces.
- 🚄 **Descargas Paralelas:** Empaqueta rápidamente grandes volúmenes de documentos en archivos ZIP empleando `ThreadPoolExecutor` (hasta 8 workers simultáneos).
- 🛡️ **Bypass Anti-Bot:** Mecanismo inteligente para abrir navegadores visibles que permiten saltar barreras de Cloudflare o CAPTCHAs antes de realizar el scraping.

### 2. Rastreo Avanzado (Deep Crawl y Paginación)
- 📑 **Paginación Automática:** Detecta links de "Siguiente" o sub-páginas en listas y las escrapea concurrentemente.
- 🔍 **Deep Crawl Asíncrono:** Utilizando `aiohttp` y `asyncio`, puede navegar hacia páginas internas de "detalle de dataset/recurso" para encontrar archivos descargables que no están a simple vista, ideal para portales gubernamentales o buscadores de datos.

### 3. Modo Portal de Datos Abiertos (Eje: datosabiertos.gob.pe)
- ⚡ **Extracción Especializada DKAN/CKAN:** Navega y parsea catálogos de datos abiertos estructurados utilizando un motor de extracción directa de HTML (que actúa como fallback robusto cuando las APIs del gobierno como la CKAN `/api/3/action/` fallan o están caídas).
- ☑️ **Vista Previa y Checkboxes:** Renderiza tablas dinámicas integradas en la interfaz de Streamlit (`st.data_editor`) que te permiten revisar y seleccionar qué documentos descargar individualmente, apoyado por una barra de progreso en vivo.

### 4. Extractor y Categorizador IA de Noticias
- 📰 **Extracción Universal de Prensa:** Motor heurístico general (no limitado a selectores fijos de cada periódico) que extrae los enlaces a las noticias interpretando las clases, tags (`<article>`) y metadatos con URLs (patrón `/YYYY/MM/DD/`).
- 🤖 **Categorización Analítica (Powered by Anthropic Claude):** Al presionar un botón, cataloga todas tus noticias en contenedores predefinidos (Política, Economía, Sociedad, Deportes, etc.) enviando la petición a la red en lotes asíncronos y limitados de 20 para cuidar tu presupuesto de Tokens.
- 📊 **Exportación Limpia:** Permite consolidar una tabla tabular (CSV con soporte nativo de UTF-8 con BOM para MS Excel) que incluye título, fecha, autor, cuerpo y categoría (IA).

---

## 🛠️ Estructura del Proyecto

```text
MineriaExam/
├── app.py                     # Interfaz central de usuario y controlador (Streamlit tabs)
├── requirements.txt           # Dependencias principales
├── scraper/
│   ├── detector.py            # Validador de tecnologías subyacentes de la página
│   ├── dynamic_scraper.py     # Chromium Headless (Playwright) - Bloquea resources para agilidad
│   ├── static_scraper.py      # Requests/BeautifulSoup Core
│   └── news_scraper.py        # Algoritmos universales para la detección y parseo de artículos
└── utils/
    ├── cleaner.py             # Sanitizador de HTML y generadores tabulares primitivos
    ├── crawler.py             # Araña web (Deep Crawl asíncrono y paginación)
    ├── extractor.py           # Empaquetador Zip paralelo para medios (Imágenes/Docs)
    ├── categorizer.py         # Lógica de Batch hacia Anthropic (Claude-Haiku 3.5)
    └── news_exporter.py       # Renderizador del Dataframe de noticias para descargas UTF-8
```

## ⚙️ Requisitos Previos e Instalación

Necesitarás **Python 3.8+** instalado.

1. **Clona el repositorio**:
   ```bash
   git clone https://github.com/eberthrosales/Scrapingexam.git
   cd Scrapingexam
   ```

2. **Instala las dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Inicia el navegador para el motor dinámico (Playwright)**:
   ```bash
   playwright install chromium
   ```

4. **Variables de Entorno (Opcionales pero recomendadas para las Noticias)**
   Para habilitar la "Categorización Mágica por IA", necesitas generar un token y exponerlo en tu entorno de terminal:
   - Para Windows (PowerShell):
     `$env:ANTHROPIC_API_KEY="sk-ant-tu-llave-api"`
   *(En caso de no colocarla, el programa sigue 100% funcional y arrojará las noticias listadas por fechas y metadata "Sin clasificar").*

## 🚀 Ejecución y Uso

Corre el servidor de desarrollo dentro del directorio base:

```bash
python -m streamlit run app.py
```

Automáticamente se abrirá en `http://localhost:8501`. 
Encontrarás **2 Pestañas Superiores**:
- **Scraper General:** Pega la url del dominio o dataset. Personaliza tu Crawl para la caza de CSVs.
- **Noticias:** Pega la sección de un portal de medios periodísticos (Ej: `https://larepublica.pe/politica`). Descarga todos sus titulares y cuerpos categorizados en un CSV con un solo click.

---
> Proyecto desarrollado utilizando metodologías agenticas basadas en LLMs para una rápida iteración de ingeniería y abstracciones de minería de datos avanzada.
