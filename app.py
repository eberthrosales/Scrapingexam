import streamlit as st
import pandas as pd
import validators
import requests
from urllib.parse import urlparse
from scraper.detector import detect_page_type
from scraper.static_scraper import scrape_static
from scraper.dynamic_scraper import scrape_dynamic
from utils.cleaner import clean_text, format_to_csv
from utils.extractor import extract_media_links, create_zip_from_urls, get_filename_from_url
from utils.crawler import get_pagination_urls, extract_deep_htmls, fetch_ckan_datasets

# Configuración de la página
st.set_page_config(
    page_title="Scraper Dinámico Universal",
    page_icon="🕸️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos personalizados (Aesthetics y Responsividad)
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: bold;
        transition: 0.3s;
    }
    .stButton>button:hover {
        opacity: 0.8;
    }
    .btn-scrape > .stButton>button {
        background-color: #ff4b4b;
        color: white;
        height: 3.5em;
        border: none;
    }
    .link-container {
        max-height: 200px;
        overflow-y: auto;
        padding: 10px;
        background-color: rgba(128,128,128,0.1);
        border-radius: 5px;
    }
    </style>
    """, unsafe_allow_html=True)


def main():
    st.title("🕸️ Scraper Dinámico Universal")
    st.markdown("Extrae texto, imágenes y documentos de cualquier sitio web de forma automática, incluyendo rastreo profundo.")

    # Sidebar para opciones
    with st.sidebar:
        st.header("Configuración de Extracción")
        st_mode = st.radio("Método de Acceso", ["Auto-detectar", "Forzar Estático", "Forzar Dinámico"])

        st.subheader("Filtros de Contenido")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            extract_text = st.checkbox("Texto/HTML", value=True)
            extract_images = st.checkbox("Imágenes", value=True)
        with col_f2:
            extract_docs = st.checkbox("Documentos/Archivos", value=True)

        filter_format = st.multiselect(
            "Filtrar por formato de documento",
            ["PDF", "CSV", "XLS", "XLSX", "JSON", "XML", "ZIP"],
            default=[],
            help="Deja vacío para incluir todos los formatos"
        )
        filter_date = st.date_input("Documentos modificados desde (solo CKAN)", value=None)

        st_clean = st.checkbox("Limpiar formato de texto", value=True, disabled=not extract_text)

        st.divider()
        st.subheader("Modo Rastreador Avanzado")
        deep_crawl = st.checkbox("🔍 Extracción Profunda (Deep Crawl)", value=False, help="Busca archivos ocultos en sub-páginas de 'Recursos'. Ideal para portales de datos abiertos.")
        max_pages = st.slider("📑 Límite de Paginación", min_value=1, max_value=10, value=1, help="Navegará por las páginas 'Siguientes' usando método extra-rápido.")

        st.divider()
        st.subheader("Modo Portal de Datos Abiertos")
        use_ckan = st.checkbox("⚡ Usar API CKAN directa (más rápido)", value=False, help="Solo funciona con datosabiertos.gob.pe. Consulta la API directamente sin scraping.")

        st.divider()
        st.info("💡 Si el sitio tiene Cloudflare o CAPTCHA, el navegador se hará visible automáticamente para que lo resuelvas (Solo válido para página inicial).")

    # Interfaz Principal y Responsiva
    with st.container():
        col1, col2 = st.columns([3, 1])

        with col1:
            url = st.text_input("🔗 Ingrese la URL del sitio web:", placeholder="https://ejemplo.com", help="Pega aquí la URL completa comenzando con http:// o https://")
            selector = st.text_input("🎯 Selector CSS (Opcional):", placeholder="ej: .noticias, #main-content, article", help="Para limitar la parte de la página a evaluar")

        with col2:
            st.write("<br><br>", unsafe_allow_html=True)
            st.markdown("<div class='btn-scrape'>", unsafe_allow_html=True)
            scrape_btn = st.button("🚀 Iniciar Scraping", use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

    if scrape_btn:
        if not url:
            st.error("Por favor, ingrese una URL válida.")
        elif not validators.url(url):
            st.error("La URL no tiene un formato válido (asegúrate de incluir http:// o https://).")
        else:
            try:
                # ══════════════════════════════════════════════════
                # MODO CKAN DIRECTO (si está activo)
                # ══════════════════════════════════════════════════
                if use_ckan and "datosabiertos.gob.pe" in url:
                    with st.spinner("Consultando API CKAN de datosabiertos.gob.pe ..."):
                        ckan_filters = {}
                        if filter_format:
                            ckan_filters["format"] = filter_format[0]  # CKAN solo filtra un formato a la vez
                        if filter_date:
                            ckan_filters["date_from"] = str(filter_date)

                        ckan_data = fetch_ckan_datasets(url, max_results=100, filters=ckan_filters if ckan_filters else None)

                    if ckan_data is not None and len(ckan_data) > 0:
                        st.success(f"✓ API CKAN: {len(ckan_data)} datasets encontrados.")

                        # Tabla resumen
                        st.markdown("### 📊 Datasets encontrados via API CKAN")
                        table_rows = []
                        all_resource_urls = []
                        for ds in ckan_data:
                            formatos = ", ".join(set(r["format"] for r in ds["resources"] if r["format"]))
                            table_rows.append({
                                "Título": ds["title"],
                                "Organización": ds["organization"],
                                "Fecha Modificación": ds["date_modified"][:10] if ds["date_modified"] else "",
                                "Formatos": formatos,
                                "Recursos": len(ds["resources"]),
                            })
                            for r in ds["resources"]:
                                if r["url"]:
                                    all_resource_urls.append(r["url"])

                        df_ckan = pd.DataFrame(table_rows)
                        st.dataframe(df_ckan, use_container_width=True)

                        # Descargar tabla como CSV
                        csv_ckan = df_ckan.to_csv(index=False)
                        st.download_button("📥 Descargar tabla CKAN como CSV", data=csv_ckan, file_name="ckan_datasets.csv", mime="text/csv", use_container_width=True, key="ckan_csv")

                        # Descargar todos los recursos
                        if all_resource_urls:
                            st.markdown(f"### 📂 Recursos descargables ({len(all_resource_urls)} archivos)")

                            # Vista previa de recursos
                            with st.expander("👁️ Vista previa de recursos encontrados"):
                                preview_rows = []
                                for r_url in all_resource_urls:
                                    fname = get_filename_from_url(r_url)
                                    ext = fname.rsplit(".", 1)[-1].upper() if "." in fname else "DESCONOCIDO"
                                    preview_rows.append({
                                        "Nombre": fname,
                                        "Tipo": ext,
                                        "URL": r_url,
                                        "Descargar": True,
                                    })

                                df_preview = pd.DataFrame(preview_rows)
                                edited_df = st.data_editor(df_preview, use_container_width=True, key="ckan_editor")

                                # Filtrar solo los marcados
                                selected_urls = [
                                    row["URL"] for _, row in edited_df.iterrows() if row["Descargar"]
                                ]

                            if selected_urls:
                                # Barra de progreso real
                                progress_bar = st.progress(0)
                                status_text = st.empty()

                                def update_progress(pct: float):
                                    progress_bar.progress(min(pct, 1.0))
                                    done = int(pct * len(selected_urls))
                                    status_text.text(f"Descargando archivo {done} de {len(selected_urls)}...")

                                zip_data = create_zip_from_urls(selected_urls, progress_callback=update_progress)
                                progress_bar.empty()
                                status_text.empty()
                                st.success(f"✓ {len(selected_urls)} recursos empaquetados correctamente.")
                                st.download_button("📦 Descargar Recursos CKAN (ZIP)", data=zip_data, file_name="ckan_recursos.zip", mime="application/zip", use_container_width=True, key="ckan_zip")

                    elif ckan_data is not None and len(ckan_data) == 0:
                        st.warning("La API CKAN no devolvió resultados con los filtros actuales.")
                    else:
                        st.warning("No se pudo conectar con la API CKAN. Cayendo al scraping normal...")
                        use_ckan_fallback = True
                    st.stop()

                # ══════════════════════════════════════════════════
                # MODO SCRAPING NORMAL
                # ══════════════════════════════════════════════════
                htmls_to_process = []

                with st.spinner(f"Accediendo a la página inicial {url} ..."):

                    # 1. Determinación del modo principal
                    if st_mode == "Auto-detectar":
                        mode = detect_page_type(url)
                    elif st_mode == "Forzar Estático":
                        mode = "static"
                    else:
                        mode = "dynamic"

                    st.write(f"✓ **Modo acceso inicial:** `{mode.capitalize()}`")

                    # 2. Ejecución del Scraping Base
                    if mode == "static":
                        result = scrape_static(url, selector)
                    else:
                        result = scrape_dynamic(url, selector)

                    if "error" in result:
                        st.error(f"Error durante el scraping: {result['error']}")
                        st.stop()

                    raw_html = result.get("html", "")
                    htmls_to_process.append(raw_html)

                # ------ CRAWLING DE PAGINACIÓN ------
                if max_pages > 1:
                    with st.spinner(f"Analizando paginación (Buscando {max_pages} páginas adicionales) ..."):
                        pagination_urls = get_pagination_urls(url, max_pages)
                        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

                        for p_url in pagination_urls:
                            try:
                                r = requests.get(p_url, headers=headers, timeout=10)
                                if r.status_code == 200:
                                    htmls_to_process.append(r.text)
                            except:
                                pass

                        if len(htmls_to_process) > 1:
                            st.success(f"✓ Paginación: {len(htmls_to_process)-1} páginas adicionales analizadas.")

                # ------ DEEP CRAWL ------
                if deep_crawl:
                    with st.spinner("Realizando Inspección Profunda (Deep Crawl) en sub-enlaces priorizados..."):
                        deep_htmls = []
                        visited_urls_set = set()
                        for h in htmls_to_process[:]:  # Solo iteramos los html top-level
                            deep_htmls.extend(extract_deep_htmls(url, h, visited_urls=visited_urls_set))

                        htmls_to_process.extend(deep_htmls)
                        if deep_htmls:
                            st.success(f"✓ Extracción Profunda: {len(deep_htmls)} sub-páginas internas de recursos visitadas.")

                st.success("¡Lectura de sitio completada con éxito!")

                # ------ PROCESAMIENTO DE TEXTO (Solo para Main Page) ------
                if extract_text:
                    st.markdown("### 📝 Contenido de Texto Principal")
                    if result.get("type") == "structured":
                        df = pd.DataFrame(result["data"])
                        st.dataframe(df, use_container_width=True)
                        csv = format_to_csv(result["data"])
                        st.download_button("Descargar Tabla como CSV", data=csv, file_name="datos_extraidos.csv", mime="text/csv", use_container_width=True)

                    if st_clean:
                        display_text = clean_text(raw_html)
                    else:
                        display_text = raw_html

                    st.text_area("Previsualización de Texto:", value=display_text, height=300)
                    st.download_button("Descargar Texto (TXT)", data=display_text, file_name="contenido_extraido.txt", mime="text/plain", use_container_width=True)

                # ------ PROCESAMIENTO DE ARCHIVOS E IMÁGENES ------
                if extract_images or extract_docs:
                    st.markdown("### 📂 Archivos y Multimedia Encontrados en todo el Rastreo")

                    # Consolidar links de todos los HTMLs procesados
                    total_img_urls: set[str] = set()
                    total_doc_urls: set[str] = set()

                    with st.spinner("Consolidando bibliotecas de medios..."):
                        for html_target in htmls_to_process:
                            media = extract_media_links(html_target, base_url=url, extract_images=extract_images, extract_documents=extract_docs)
                            total_img_urls.update(media["imagenes"])
                            total_doc_urls.update(media["documentos"])

                    img_urls = list(total_img_urls)
                    doc_urls = list(total_doc_urls)

                    # Aplicar filtro por formato si se especificó
                    if filter_format and doc_urls:
                        allowed_extensions = tuple(f".{fmt.lower()}" for fmt in filter_format)
                        doc_urls = [u for u in doc_urls if urlparse(u).path.lower().endswith(allowed_extensions)]

                    c1, c2 = st.columns(2)

                    with c1:
                        if extract_images:
                            st.subheader(f"🖼️ Imágenes ({len(img_urls)})")
                            if img_urls:
                                with st.expander("Ver lista de imágenes"):
                                    st.write(img_urls)

                                # Barra de progreso real para imágenes
                                progress_bar_img = st.progress(0)
                                status_text_img = st.empty()

                                def update_img_progress(pct: float):
                                    progress_bar_img.progress(min(pct, 1.0))
                                    done = int(pct * len(img_urls))
                                    status_text_img.text(f"Descargando imagen {done} de {len(img_urls)}...")

                                zip_imgs = create_zip_from_urls(img_urls, progress_callback=update_img_progress)
                                progress_bar_img.empty()
                                status_text_img.empty()
                                st.success(f"✓ {len(img_urls)} imágenes empaquetadas.")
                                st.download_button("📦 Descargar Imágenes (ZIP)", data=zip_imgs, file_name="imagenes_extraidas.zip", mime="application/zip", use_container_width=True, key="img_zip")
                            else:
                                st.info("No se encontraron imágenes descargables.")

                    with c2:
                        if extract_docs:
                            st.subheader(f"📄 Documentos ({len(doc_urls)})")
                            if doc_urls:
                                # Vista previa de documentos con selección
                                with st.expander("👁️ Vista previa de documentos encontrados"):
                                    preview_rows = []
                                    for d_url in doc_urls:
                                        fname = get_filename_from_url(d_url)
                                        ext = fname.rsplit(".", 1)[-1].upper() if "." in fname else "DESCONOCIDO"
                                        preview_rows.append({
                                            "Nombre": fname,
                                            "Tipo": ext,
                                            "URL": d_url,
                                            "Descargar": True,
                                        })
                                    df_docs = pd.DataFrame(preview_rows)
                                    edited_docs = st.data_editor(df_docs, use_container_width=True, key="doc_editor")

                                    # Filtrar solo los que el usuario marcó
                                    selected_doc_urls = [
                                        row["URL"] for _, row in edited_docs.iterrows() if row["Descargar"]
                                    ]

                                if selected_doc_urls:
                                    # Barra de progreso real para documentos
                                    progress_bar_doc = st.progress(0)
                                    status_text_doc = st.empty()

                                    def update_doc_progress(pct: float):
                                        progress_bar_doc.progress(min(pct, 1.0))
                                        done = int(pct * len(selected_doc_urls))
                                        status_text_doc.text(f"Descargando archivo {done} de {len(selected_doc_urls)}...")

                                    zip_docs = create_zip_from_urls(selected_doc_urls, progress_callback=update_doc_progress)
                                    progress_bar_doc.empty()
                                    status_text_doc.empty()
                                    st.success(f"✓ {len(selected_doc_urls)} documentos empaquetados.")
                                    st.download_button("📦 Descargar Documentos (ZIP)", data=zip_docs, file_name="documentos_extraidos.zip", mime="application/zip", use_container_width=True, key="doc_zip")
                                else:
                                    st.warning("No se seleccionaron documentos para descargar.")
                            else:
                                st.info("No se encontraron documentos descargables. (Activa Deep Crawl si crees que están ocultos)")

            except Exception as e:
                st.error(f"Ocurrió un error inesperado al procesar: {str(e)}")


if __name__ == "__main__":
    main()
