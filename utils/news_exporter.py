import pandas as pd


def export_news_to_csv(articles: list[dict]) -> bytes:
    """
    Convierte la lista de artículos de noticias a un CSV descargable.
    Encoding UTF-8 con BOM para compatibilidad con Excel en español.
    Retorna bytes para usar directamente en st.download_button.
    """
    rows: list[dict] = []
    for art in articles:
        rows.append({
            "titulo": art.get("titulo", ""),
            "fecha": art.get("fecha", ""),
            "autor": art.get("autor", "Desconocido"),
            "categoria_ia": art.get("categoria_ia", ""),
            "tags_originales": " | ".join(art.get("tags_originales", [])),
            "resumen": art.get("resumen", ""),
            "cuerpo": art.get("cuerpo", ""),
            "url_fuente": art.get("url_fuente", ""),
            "imagenes": " | ".join(art.get("imagenes", [])),
        })

    df = pd.DataFrame(rows, columns=[
        "titulo", "fecha", "autor", "categoria_ia", "tags_originales",
        "resumen", "cuerpo", "url_fuente", "imagenes"
    ])

    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
