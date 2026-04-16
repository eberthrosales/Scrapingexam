import os
import json
import warnings
from typing import Optional


def categorize_articles(articles: list[dict]) -> list[dict]:
    """
    Categoriza una lista de artículos de noticias usando la API de Anthropic (Claude).
    Si la API key no está configurada, asigna 'Sin clasificar' a todos.
    Procesa en lotes de 20 para no exceder tokens.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        warnings.warn(
            "ANTHROPIC_API_KEY no está configurada. Se asignará 'Sin clasificar' a todos los artículos.",
            UserWarning
        )
        for article in articles:
            article["categoria_ia"] = "Sin clasificar"
        return articles

    # Procesar en lotes de 20
    batch_size = 20
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        _categorize_batch(batch, i, api_key)

    return articles


CATEGORIAS_VALIDAS = [
    "Política", "Economía", "Tecnología", "Salud", "Educación",
    "Medio Ambiente", "Cultura y Entretenimiento", "Deportes",
    "Seguridad y Justicia", "Internacional", "Sociedad", "Ciencia", "Otros"
]


def _categorize_batch(batch: list[dict], start_index: int, api_key: str) -> None:
    """
    Envía un lote de artículos a Claude para categorización.
    Modifica los dicts in-place, añadiendo 'categoria_ia'.
    """
    # Construir el resumen del lote para el prompt
    articles_text = ""
    for idx, art in enumerate(batch):
        titulo = art.get("titulo", "Sin título")
        resumen = art.get("resumen", "")[:200]
        articles_text += f"[{idx}] Título: {titulo}\nResumen: {resumen}\n\n"

    prompt = f"""Eres un clasificador de noticias. Para cada artículo que te presento, asigna UNA SOLA categoría de esta lista fija:

Categorías permitidas:
- Política
- Economía
- Tecnología
- Salud
- Educación
- Medio Ambiente
- Cultura y Entretenimiento
- Deportes
- Seguridad y Justicia
- Internacional
- Sociedad
- Ciencia
- Otros

Artículos a clasificar:

{articles_text}

Responde SOLAMENTE con un JSON válido (sin texto antes ni después), con este formato exacto:
[{{"index": 0, "categoria": "Política"}}, {{"index": 1, "categoria": "Economía"}}]

Incluye todos los artículos del 0 al {len(batch) - 1}."""

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-haiku-3-5",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Extraer el texto de la respuesta
        response_text = message.content[0].text.strip()

        # Intentar parsear JSON (a veces el modelo mete texto extra)
        # Buscar el array JSON dentro de la respuesta
        json_match = _extract_json_array(response_text)
        if json_match:
            categorias = json.loads(json_match)
            for item in categorias:
                idx = item.get("index", -1)
                cat = item.get("categoria", "Otros")
                if 0 <= idx < len(batch):
                    if cat in CATEGORIAS_VALIDAS:
                        batch[idx]["categoria_ia"] = cat
                    else:
                        batch[idx]["categoria_ia"] = "Otros"

        # Rellenar los que no se clasificaron
        for art in batch:
            if not art.get("categoria_ia"):
                art["categoria_ia"] = "Otros"

    except Exception as e:
        print(f"Error en categorización IA (lote desde índice {start_index}): {e}")
        for art in batch:
            art["categoria_ia"] = "Otros"


def _extract_json_array(text: str) -> Optional[str]:
    """Extrae el primer array JSON válido de un texto."""
    # Buscar el primer [ y el último ]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return None
