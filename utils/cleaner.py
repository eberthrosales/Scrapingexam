import re
from bs4 import BeautifulSoup
import io
import csv

def clean_text(html_content):
    """
    Limpia el contenido HTML para extraer solo el texto relevante.
    Elimina scripts, estilos y etiquetas de navegación comunes.
    """
    if not html_content:
        return ""
    
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Eliminar elementos que no contienen contenido textual útil
    for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
        element.decompose()
        
    # Obtener texto
    text = soup.get_text(separator="\n")
    
    # Limpiar espacios en blanco excesivos
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = "\n".join(chunk for chunk in chunks if chunk)
    
    return text

def format_to_csv(data_dict_list):
    """
    Convierte una lista de diccionarios en un string formato CSV.
    """
    if not data_dict_list:
        return ""
    
    output = io.StringIO()
    keys = data_dict_list[0].keys()
    dict_writer = csv.DictWriter(output, fieldnames=keys)
    dict_writer.writeheader()
    dict_writer.writerows(data_dict_list)
    
    return output.getvalue()
