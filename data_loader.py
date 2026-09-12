"""
data_loader.py
================
Este archivo tiene UNA sola responsabilidad: leer los datos "en crudo"
(tal como vienen del Excel) y devolverlos como una tabla (DataFrame de
pandas) con nombres de columna ya normalizados (sin saltos de línea,
sin espacios raros al principio/final, sin el caracter invisible \\xa0
que Google Forms suele meter en los encabezados).

¿Por qué está separado del resto de la app?
--------------------------------------------
Hoy los datos vienen de un archivo Excel local. Más adelante el grupo
podría querer leerlos directamente de un Google Sheet o de una base de
datos. Si TODO el código que "sabe leer un Excel" vive únicamente en
la función `load_data`, el día de mañana basta con reescribir esa
función (por ejemplo usando la librería `gspread` para Google Sheets)
sin tocar ni una línea del resto de la aplicación (limpieza, matching,
mapa, etc.), porque todo lo demás solo espera recibir un DataFrame con
columnas ya normalizadas.
"""

from __future__ import annotations

import re
import unicodedata

import pandas as pd

# Ruta por defecto del archivo Excel dentro del proyecto.
# Se puede sobreescribir pasando otra ruta a load_data().
RUTA_EXCEL_POR_DEFECTO = "data/Inscripcion_Nivel_1_Consultorio_Contable.xlsx"


def _normalizar_nombre_columna(nombre: str) -> str:
    """Limpia el texto de un encabezado de columna.

    Los formularios de Google a veces exportan encabezados con:
    - saltos de línea "\\n" dentro del texto,
    - el caracter "espacio de no separación" (\\xa0),
    - espacios dobles o al principio/final.
    Esta función deja el texto "plano" y comparable, sin cambiar el
    significado (no se traduce ni se resume, solo se limpia el formato).
    """
    if not isinstance(nombre, str):
        return nombre
    texto = nombre.replace("\xa0", " ")  # espacio invisible -> espacio normal
    texto = texto.replace("\n", " ").replace("\r", " ")
    texto = re.sub(r"\s+", " ", texto)  # varios espacios seguidos -> uno solo
    return texto.strip()


def load_data(ruta_excel: str = RUTA_EXCEL_POR_DEFECTO) -> pd.DataFrame:
    """Lee el Excel de inscripciones y devuelve un DataFrame "en crudo".

    "En crudo" quiere decir: todavía puede tener filas vacías, teléfonos
    mal formateados, ciudades escritas de formas distintas, personas
    duplicadas, etc. Ese trabajo de limpieza lo hace el módulo
    `procesamiento.py`, no este archivo.

    Parámetros
    ----------
    ruta_excel: ruta (relativa o absoluta) al archivo .xlsx a leer.

    Si en el futuro se reemplaza el origen de datos (por ejemplo por
    Google Sheets), esta es la única función que hay que reescribir:
    debe seguir devolviendo un DataFrame con las mismas columnas
    (una vez normalizadas), y todo el resto de la app seguirá
    funcionando igual.
    """
    df = pd.read_excel(ruta_excel)
    df.columns = [_normalizar_nombre_columna(c) for c in df.columns]
    return df


def normalizar_texto(texto: object) -> str:
    """Convierte cualquier texto a una forma "comparable":

    - todo en mayúsculas,
    - sin tildes/acentos (á -> A, ñ -> N, etc.),
    - sin signos de puntuación (solo letras, números y espacios),
    - sin espacios repetidos.

    Se usa tanto para limpiar lo que escribió la gente en el formulario
    como para preparar los nombres oficiales de municipios/departamentos,
    de modo que se puedan comparar "en igualdad de condiciones".
    """
    # ¡Ojo! Un campo vacío del Excel llega aquí como NaN (float), no
    # como None. Si no lo detectamos con pd.isna(), Python lo convierte
    # con str() en el texto "nan", que por casualidad se parece mucho
    # a nombres reales de municipios (ej. "SAN FERNANDO" contiene "NAN")
    # y termina generando coincidencias falsas.
    if texto is None or pd.isna(texto):
        return ""
    texto = str(texto).strip().upper()
    # NFKD separa la letra de su tilde (á -> a + ´) y luego descartamos
    # los caracteres de acentuación (unicodedata.combining).
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^A-Z0-9\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto
