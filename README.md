# Scraper Dinámico Universal 🕸️

Este proyecto es una aplicación web potente y versátil construida con **Python** y **Streamlit** que permite realizar scraping de prácticamente cualquier sitio web, detectando automáticamente si el contenido es estático o requiere renderizado dinámico (JavaScript).

## Características Principales

- 🤖 **Detección Automática**: Identifica si una página es estática o dinámica para usar la mejor herramienta de extracción.
- 🎭 **Modo Playwright**: Maneja sitios web complejos basados en React, Vue, Angular, etc.
- 🛡️ **Evasión de Bloqueos**: Detección de Cloudflare y CAPTCHAs con apertura automática de navegador para intervención manual.
- 📂 **Extracción Multimedia**: Descarga no solo texto, sino también imágenes y documentos (PDF, Excel, Word, etc.) en un archivo ZIP.
- 🎯 **Selector CSS**: Permite filtrar la extracción a elementos específicos del DOM.
- 📱 **Interfaz Responsiva**: Diseñada para verse bien en cualquier dispositivo.

## Requisitos Previos

Asegúrate de tener Python 3.8+ instalado en tu sistema.

## Instalación

1. **Clona el repositorio** (si aún no lo has hecho):
   ```bash
   git clone https://github.com/eberthrosales/Scrapingexam.git
   cd Scrapingexam
   ```

2. **Instala las dependencias de Python**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Instala los navegadores necesarios para Playwright**:
   ```bash
   playwright install chromium
   ```

## Ejecución

Para iniciar la aplicación, ejecuta el siguiente comando en tu terminal:

```bash
python -m streamlit run app.py
```

La aplicación se abrirá automáticamente en tu navegador predeterminado (usualmente en `http://localhost:8501`).

## Estructura del Proyecto

- `app.py`: Interfaz de usuario principal.
- `scraper/`:
  - `detector.py`: Lógica para detectar el tipo de página.
  - `static_scraper.py`: Extracción usando Requests y BeautifulSoup.
  - `dynamic_scraper.py`: Extracción usando Playwright.
- `utils/`:
  - `cleaner.py`: Limpieza de texto y formateo.
  - `extractor.py`: Extracción de archivos multimedia y generación de ZIP.

---
Desarrollado para la extracción eficiente y universal de datos web.
