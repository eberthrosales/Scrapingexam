import streamlit as st
import pandas as pd
import validators
from scraper.detector import detect_page_type
from scraper.static_scraper import scrape_static
from scraper.dynamic_scraper import scrape_dynamic
from utils.cleaner import clean_text, format_to_csv
from utils.extractor import extract_media_links, create_zip_from_urls

# Configuración de la página
st.set_page_config(
    page_title="Scraper Dinámico Universal",
    page_icon="🕸️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos personalizados (Aesthetics y Responsividad)
# NOTA: Removido el color de fuente estático en el stTextInput para evitar 
# que se vea blanco sobre blanco en el tema claro de Streamlit.
st.markdown("""
    <style>
    /* Mejoramos el layout general usando los temas nativos pero dando acentos */
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
    st.markdown("Extrae texto, imágenes y documentos de cualquier sitio web de forma automática.")
    
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
            
        st_clean = st.checkbox("Limpiar formato de texto", value=True, disabled=not extract_text)
        
        st.divider()
        st.info("💡 Si el sitio tiene Cloudflare o CAPTCHA, el navegador se hará visible automáticamente para que lo resuelvas.")

    # Interfaz Principal y Responsiva: Usamos containers y columns
    with st.container():
        col1, col2 = st.columns([3, 1])
        
        with col1:
            url = st.text_input("🔗 Ingrese la URL del sitio web:", placeholder="https://ejemplo.com", help="Pega aquí la URL completa comenzando con http:// o https://")
            selector = st.text_input("🎯 Selector CSS (Opcional):", placeholder="ej: .noticias, #main-content, article", help="Para limitar la parte de la página a evaluar")
            
        with col2:
            st.write("<br><br>", unsafe_allow_html=True) # Espaciador para alinear con los inputs
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
                with st.spinner(f"Analizando y extrayendo {url} ..."):
                    
                    # 1. Determinación del modo
                    if st_mode == "Auto-detectar":
                        mode = detect_page_type(url)
                    elif st_mode == "Forzar Estático":
                        mode = "static"
                    else:
                        mode = "dynamic"
                    
                    st.write(f"✓ **Modo detectado/utilizado:** `{mode.capitalize()}`")
                    
                    # 2. Ejecución del Scraping Base
                    if mode == "static":
                        result = scrape_static(url, selector)
                    else:
                        result = scrape_dynamic(url, selector)
                    
                    # 3. Manejo de resultados base
                    if "error" in result:
                        st.error(f"Error durante el scraping: {result['error']}")
                        st.stop()
                    
                    st.success("¡Lectura de página completada con éxito!")
                    raw_html = result.get("html", "")
                    
                    # ------ PROCESAMIENTO DE TEXTO ------
                    if extract_text:
                        st.markdown("### 📝 Contenido de Texto")
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
                        st.markdown("### 📂 Archivos y Multimedia Encontrados")
                        
                        media = extract_media_links(raw_html, base_url=url, extract_images=extract_images, extract_documents=extract_docs)
                        
                        img_urls = list(media["imagenes"])
                        doc_urls = list(media["documentos"])
                        
                        c1, c2 = st.columns(2)
                        
                        with c1:
                            if extract_images:
                                st.subheader(f"🖼️ Imágenes ({len(img_urls)})")
                                if img_urls:
                                    with st.expander("Ver lista de imágenes"):
                                        st.write(img_urls)
                                    
                                    with st.spinner("Empaquetando imágenes (esto puede tardar si hay muchas)..."):
                                        zip_imgs = create_zip_from_urls(img_urls)
                                    st.download_button("📦 Descargar Imágenes (ZIP)", data=zip_imgs, file_name="imagenes_extraidas.zip", mime="application/zip", use_container_width=True)
                                else:
                                    st.info("No se encontraron imágenes en el área seleccionada.")
                        
                        with c2:
                            if extract_docs:
                                st.subheader(f"📄 Documentos ({len(doc_urls)})")
                                if doc_urls:
                                    with st.expander("Ver lista de documentos"):
                                        st.write(doc_urls)
                                        
                                    with st.spinner("Empaquetando documentos..."):
                                        zip_docs = create_zip_from_urls(doc_urls)
                                    st.download_button("📦 Descargar Documentos (ZIP)", data=zip_docs, file_name="documentos_extraidos.zip", mime="application/zip", use_container_width=True)
                                else:
                                    st.info("No se encontraron documentos descargables.")

            except Exception as e:
                st.error(f"Ocurrió un error inesperado al procesar: {str(e)}")

if __name__ == "__main__":
    main()
