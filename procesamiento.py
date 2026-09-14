"""
procesamiento.py
==================
Este módulo toma el DataFrame "en crudo" que devuelve `data_loader.py`
y lo transforma en algo listo para mostrar en el mapa:

1. Descarta filas vacías/incompletas y duplicados por identificación.
2. Limpia el teléfono (le quita el ".0" que a veces mete Excel).
3. Arma una sola columna de "ciudad" y "modalidad" combinando las
   preguntas de modalidad virtual y presencial (cada inscrito solo
   contestó una de las dos, según cómo iba a participar).
4. Usa el emparejamiento difuso (emparejamiento_municipios.py) para
   convertir el texto libre de ciudad en un municipio + departamento
   oficiales.
5. Agrega (cuenta personas) por municipio y por departamento.

Nada de esto sabe leer un Excel ni un Google Sheet: solo trabaja sobre
el DataFrame que le llega. Así, si el día de mañana `data_loader.py`
cambia su fuente de datos, este archivo no necesita tocarse.
"""

from __future__ import annotations

import pandas as pd

from emparejamiento_municipios import emparejar_ciudad
from referencia_geografica import Municipio, construir_indice_departamentos

# --- Nombres de columnas del Excel (ya normalizados por data_loader) ---
COL_ID = "ID"
COL_HORA_INICIO = "Hora de inicio"
COL_NOMBRE = "Nombres y apellidos completos del usuario- Favor colocarlos con mayúsculas, minúsculas y tildes."
COL_IDENTIFICACION = "Número de Identificación"
COL_TELEFONO = "Teléfono o Celular"
COL_MODALIDAD = "Modalidad de capacitación"
COL_CIUDAD_VIRTUAL = "¿Desde qué ciudad o municipio se conecta VIRTUALMENTE para recibir las clases?"
COL_CIUDAD_PRESENCIAL = "¿Desde qué Ciudad se va ha participar PRESENCIALMENTE a las clases?"
# Estas dos preguntas de "Localidad" SÍ traen datos útiles (a diferencia
# de las columnas duplicadas del mismo nombre, que quedaron casi vacías
# porque el formulario las repitió por error). Además, a diferencia de
# "ciudad", esta pregunta era una lista desplegable de opciones fijas
# (las 20 localidades oficiales de Bogotá D.C.), así que no trae errores
# de digitación y no necesita coincidencia aproximada.
COL_LOCALIDAD_VIRTUAL = "¿Desde qué Localidad va a participar VIRTUALMENTE para recibir las clases?"
COL_LOCALIDAD_PRESENCIAL = "¿Desde qué Localidad se va a participar PRESENCIALMENTE a las clases?"

MODALIDAD_VIRTUAL = "Virtual"
MODALIDAD_PRESENCIAL = "Presencial"
BOGOTA_DC = "Bogotá D.C."


def limpiar_telefono(valor: object) -> str | None:
    """Deja el teléfono como texto de solo dígitos.

    Cuando Excel interpreta una columna de teléfonos como número, a
    veces agrega un ".0" al final (ej. "3133448625.0"). También puede
    venir con espacios, guiones o el prefijo "+57". Esta función
    limpia todo eso y deja solo los dígitos.
    """
    if pd.isna(valor):
        return None
    texto = str(valor).strip()
    if texto.endswith(".0"):
        texto = texto[:-2]
    texto = "".join(c for c in texto if c.isdigit())
    return texto or None


def _detectar_modalidad(valor_modalidad: object) -> str | None:
    """Convierte el texto largo de la pregunta de modalidad
    ("Virtual (se llevará a cabo por medio de la plataforma Zoom)")
    en una sola palabra: "Virtual" o "Presencial".
    """
    if pd.isna(valor_modalidad):
        return None
    texto = str(valor_modalidad).strip().lower()
    if texto.startswith("virtual"):
        return MODALIDAD_VIRTUAL
    if texto.startswith("presencial"):
        return MODALIDAD_PRESENCIAL
    return None


def descartar_incompletos_y_duplicados(df: pd.DataFrame) -> pd.DataFrame:
    """Quita:
    - Filas sin nombre y sin número de identificación (inscripciones
      que quedaron a medias y nunca se terminaron de llenar).
    - Filas duplicadas por número de identificación (alguien que se
      inscribió más de una vez), quedándonos con la más reciente según
      "Hora de inicio".
    """
    df = df.copy()

    df = df.dropna(subset=[COL_NOMBRE, COL_IDENTIFICACION], how="all")

    if COL_HORA_INICIO in df.columns:
        df = df.sort_values(COL_HORA_INICIO)

    df = df.drop_duplicates(subset=[COL_IDENTIFICACION], keep="last")

    return df


def construir_columna_ciudad_y_modalidad(df: pd.DataFrame) -> pd.DataFrame:
    """Crea columnas nuevas y sencillas:
    - "modalidad": "Virtual" o "Presencial".
    - "ciudad_texto_original": lo que la persona escribió como ciudad,
      tomado de la pregunta virtual o presencial según corresponda.
    - "localidad": la localidad de Bogotá (si la persona vive en Bogotá
      y contestó esa pregunta), también elegida entre la versión
      virtual o presencial según la modalidad.
    """
    df = df.copy()
    df["modalidad"] = df[COL_MODALIDAD].apply(_detectar_modalidad)

    def elegir_ciudad(fila):
        if fila["modalidad"] == MODALIDAD_PRESENCIAL:
            return fila.get(COL_CIUDAD_PRESENCIAL)
        return fila.get(COL_CIUDAD_VIRTUAL)

    def elegir_localidad(fila):
        if fila["modalidad"] == MODALIDAD_PRESENCIAL:
            return fila.get(COL_LOCALIDAD_PRESENCIAL)
        return fila.get(COL_LOCALIDAD_VIRTUAL)

    df["ciudad_texto_original"] = df.apply(elegir_ciudad, axis=1)
    df["localidad"] = df.apply(elegir_localidad, axis=1)
    df["localidad"] = df["localidad"].apply(lambda v: str(v).strip() if pd.notna(v) else None)
    return df


def aplicar_emparejamiento_municipios(
    df: pd.DataFrame, municipios: list[Municipio]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Le agrega a cada fila su municipio/departamento oficial,
    usando coincidencia aproximada sobre "ciudad_texto_original".

    Devuelve dos DataFrames:
    - el DataFrame original con las columnas nuevas
      (municipio, departamento, departamento_codigo, match_score, match_estado)
    - una tabla aparte solo con los valores que NO se pudieron
      emparejar con confianza, para revisar a mano.
    """
    indice_departamentos = construir_indice_departamentos(municipios)

    resultados = df["ciudad_texto_original"].apply(
        lambda texto: emparejar_ciudad(texto, municipios, indice_departamentos)
    )

    df = df.copy()
    df["municipio"] = [r.municipio for r in resultados]
    df["departamento"] = [r.departamento for r in resultados]
    df["departamento_codigo"] = [r.departamento_codigo for r in resultados]
    df["match_score"] = [r.score for r in resultados]
    df["match_estado"] = [r.estado for r in resultados]

    sin_emparejar = (
        df[df["match_estado"].isin(["sin_match", "vacio"])][
            ["ciudad_texto_original", "modalidad", "match_score", "match_estado"]
        ]
        .drop_duplicates(subset=["ciudad_texto_original"])
        .sort_values("ciudad_texto_original")
        .reset_index(drop=True)
    )

    return df, sin_emparejar


def procesar_inscripciones(
    df_crudo: pd.DataFrame, municipios: list[Municipio]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Función "orquestadora": aplica, en orden, todos los pasos de
    limpieza sobre el DataFrame crudo y devuelve la tabla final lista
    para agregar y graficar, junto con la tabla de valores sin emparejar.
    """
    df = descartar_incompletos_y_duplicados(df_crudo)
    df["anio"] = pd.to_datetime(df[COL_HORA_INICIO], errors="coerce").dt.year.astype("Int64")
    df[COL_TELEFONO] = df[COL_TELEFONO].apply(limpiar_telefono)
    df = construir_columna_ciudad_y_modalidad(df)
    df, sin_emparejar = aplicar_emparejamiento_municipios(df, municipios)
    return df, sin_emparejar


def agregar_por_municipio(df: pd.DataFrame) -> pd.DataFrame:
    """Cuenta cuántas personas hay por municipio (con su departamento),
    ordenado de mayor a menor cantidad. Solo tiene en cuenta filas que
    sí pudieron emparejarse a un municipio concreto (match_estado == "ok"),
    para no mezclar "personas reales de un municipio" con "personas de
    las que solo sabemos el departamento".
    """
    datos = df[df["match_estado"] == "ok"]
    conteo = (
        datos.groupby(["municipio", "departamento", "departamento_codigo"])
        .size()
        .reset_index(name="personas")
        .sort_values("personas", ascending=False)
        .reset_index(drop=True)
    )
    return conteo


def agregar_por_departamento(df: pd.DataFrame) -> pd.DataFrame:
    """Cuenta cuántas personas hay por departamento. A diferencia de
    `agregar_por_municipio`, aquí SÍ incluimos las filas marcadas como
    "solo_departamento" (sabemos el departamento aunque no el
    municipio exacto), porque para el mapa por departamento esa
    información sigue siendo válida y no queremos subestimar el total.
    """
    datos = df[df["match_estado"].isin(["ok", "solo_departamento"])]
    conteo = (
        datos.groupby(["departamento", "departamento_codigo"])
        .size()
        .reset_index(name="personas")
        .sort_values("personas", ascending=False)
        .reset_index(drop=True)
    )
    return conteo


def agregar_por_anio(df: pd.DataFrame) -> pd.DataFrame:
    """Cuenta las inscripciones depuradas por año.

    El año se obtiene de "Hora de inicio". Las filas sin una fecha válida
    se excluyen porque no pueden ubicarse correctamente en el eje temporal.
    """
    datos = df.dropna(subset=["anio"])
    conteo = (
        datos.groupby("anio")
        .size()
        .reset_index(name="personas")
        .sort_values("anio")
        .reset_index(drop=True)
    )
    conteo["anio"] = conteo["anio"].astype(int).astype(str)
    return conteo


def agregar_por_localidad_bogota(df: pd.DataFrame) -> pd.DataFrame:
    """Cuenta cuántas personas hay por localidad, SOLO para quienes
    quedaron ubicados en Bogotá D.C. y sí contestaron la pregunta de
    localidad (no todo el mundo la contestó).
    """
    datos = df[(df["municipio"] == BOGOTA_DC) & df["localidad"].notna()]
    conteo = (
        datos.groupby("localidad")
        .size()
        .reset_index(name="personas")
        .sort_values("personas", ascending=False)
        .reset_index(drop=True)
    )
    return conteo
