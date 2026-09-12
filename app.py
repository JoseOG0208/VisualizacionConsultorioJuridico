"""
app.py
=======
Esta es la aplicación de Streamlit. Es el único archivo que se ejecuta
directamente (con `streamlit run app.py`); todo lo demás son módulos
de apoyo que este archivo importa:

- data_loader.py            -> lee el Excel "en crudo".
- referencia_geografica.py  -> carga la tabla oficial de municipios y
                                el mapa (GeoJSON) de departamentos.
- emparejamiento_municipios.py -> adivina a qué municipio corresponde
                                cada texto libre de ciudad.
- procesamiento.py          -> limpia, deduplica y agrega los datos.

La idea es que este archivo se concentre SOLO en la interfaz (qué se
ve en pantalla) y delegue todo el trabajo "de datos" a los módulos de
arriba.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from data_loader import RUTA_EXCEL_POR_DEFECTO, load_data
from procesamiento import (
    agregar_por_departamento,
    agregar_por_localidad_bogota,
    agregar_por_municipio,
    procesar_inscripciones,
)
from referencia_geografica import (
    RUTA_GEOJSON_DEPARTAMENTOS,
    cargar_geojson_departamentos,
    cargar_municipios,
    listar_todos_los_departamentos,
)

st.set_page_config(
    page_title="Mapa Consultorio Contable Javeriano",
    page_icon="🗺️",
    layout="wide",
)


# ---------------------------------------------------------------------------
# CARGA Y PROCESAMIENTO DE DATOS (con caché)
# ---------------------------------------------------------------------------
# @st.cache_data hace que Streamlit "recuerde" el resultado de la función
# la primera vez que se ejecuta. Si el usuario solo cambia un filtro en
# la pantalla (por ejemplo, la modalidad), Streamlit vuelve a correr
# todo el script de arriba a abajo, pero SIN repetir el trabajo pesado
# de leer el Excel y hacer el fuzzy-matching, porque ya está guardado
# en caché. Esto hace que la app se sienta rápida.
#
# El caché se invalida solo (y se vuelve a calcular) si cambian los
# argumentos de la función, por ejemplo si se sube un Excel distinto.


@st.cache_data(show_spinner="Leyendo el archivo Excel...")
def obtener_datos_crudos(ruta_excel: str) -> pd.DataFrame:
    return load_data(ruta_excel)


@st.cache_data(show_spinner="Cargando tabla oficial de municipios...")
def obtener_referencia_geografica():
    municipios = cargar_municipios()
    geojson = cargar_geojson_departamentos(RUTA_GEOJSON_DEPARTAMENTOS)
    return municipios, geojson


@st.cache_data(show_spinner="Limpiando datos y emparejando ciudades...")
def obtener_datos_procesados(ruta_excel: str):
    df_crudo = obtener_datos_crudos(ruta_excel)
    municipios, _ = obtener_referencia_geografica()
    df, sin_emparejar = procesar_inscripciones(df_crudo, municipios)
    return df, sin_emparejar


# ---------------------------------------------------------------------------
# BARRA LATERAL: de dónde sacar los datos
# ---------------------------------------------------------------------------
st.sidebar.header("Fuente de datos")
archivo_subido = st.sidebar.file_uploader(
    "Sube un Excel de inscripción (opcional)", type=["xlsx"]
)

# Si el usuario sube su propio archivo lo usamos; si no, usamos el que
# viene incluido en la carpeta data/ del proyecto.
ruta_excel_a_usar = archivo_subido if archivo_subido is not None else RUTA_EXCEL_POR_DEFECTO

try:
    df, sin_emparejar = obtener_datos_procesados(ruta_excel_a_usar)
    _, geojson_departamentos = obtener_referencia_geografica()
except FileNotFoundError:
    st.error(
        f"No se encontró el archivo '{RUTA_EXCEL_POR_DEFECTO}'. "
        "Sube un Excel desde la barra lateral o coloca el archivo en la carpeta 'data/'."
    )
    st.stop()


# ---------------------------------------------------------------------------
# TÍTULO Y FILTROS
# ---------------------------------------------------------------------------
st.title("🗺️ Mapa de participación — Consultorio Contable Javeriano")
st.caption(
    "Cantidad de personas inscritas a las capacitaciones, por ciudad/municipio "
    "y departamento de Colombia."
)

col_filtro_modalidad, col_filtro_busqueda = st.columns([1, 2])

with col_filtro_modalidad:
    modalidad_seleccionada = st.selectbox(
        "Modalidad de capacitación",
        options=["Todas", "Virtual", "Presencial"],
        index=0,
    )

with col_filtro_busqueda:
    texto_busqueda = st.text_input(
        "Buscar municipio (opcional)",
        placeholder="Ej: Armenia, Bogotá, Soacha...",
    )

# Aplicamos el filtro de modalidad sobre los datos ya procesados.
if modalidad_seleccionada == "Todas":
    df_filtrado = df
else:
    df_filtrado = df[df["modalidad"] == modalidad_seleccionada]

conteo_departamentos = agregar_por_departamento(df_filtrado)
conteo_municipios = agregar_por_municipio(df_filtrado)

if texto_busqueda.strip():
    conteo_municipios = conteo_municipios[
        conteo_municipios["municipio"].str.contains(texto_busqueda.strip(), case=False, na=False)
    ]


# ---------------------------------------------------------------------------
# MÉTRICAS RÁPIDAS
# ---------------------------------------------------------------------------
total_personas = len(df_filtrado)
total_con_ubicacion = conteo_departamentos["personas"].sum()
total_municipios_distintos = df_filtrado.loc[df_filtrado["match_estado"] == "ok", "municipio"].nunique()

col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("Personas inscritas (filtro actual)", total_personas)
col_m2.metric("Con ciudad/departamento identificado", int(total_con_ubicacion))
col_m3.metric("Municipios distintos representados", total_municipios_distintos)


# ---------------------------------------------------------------------------
# MAPA COROPLÉTICO POR DEPARTAMENTO
# ---------------------------------------------------------------------------
st.subheader("Mapa por departamento")

# Completamos con los 33 departamentos (incluso los que tienen 0
# personas) para que el mapa siempre muestre la silueta completa de
# Colombia, en vez de recortarse solo a la zona donde hay datos.
todos_los_departamentos, _ = obtener_referencia_geografica()
todos_los_departamentos = listar_todos_los_departamentos(todos_los_departamentos)
conteo_departamentos_mapa = todos_los_departamentos.merge(
    conteo_departamentos[["departamento_codigo", "personas"]],
    on="departamento_codigo",
    how="left",
)
conteo_departamentos_mapa["personas"] = conteo_departamentos_mapa["personas"].fillna(0).astype(int)

# Escala de color "secuencial" (un solo tono, de claro a oscuro) para
# representar una magnitud (cantidad de personas). Se evita a propósito
# una escala tipo "arcoíris": con una magnitud, el ojo debe poder leer
# "más oscuro = más personas" sin tener que consultar la leyenda.
ESCALA_AZUL_SECUENCIAL = [
    [0 / 12, "#cde2fb"],
    [1 / 12, "#b7d3f6"],
    [2 / 12, "#9ec5f4"],
    [3 / 12, "#86b6ef"],
    [4 / 12, "#6da7ec"],
    [5 / 12, "#5598e7"],
    [6 / 12, "#3987e5"],
    [7 / 12, "#2a78d6"],
    [8 / 12, "#256abf"],
    [9 / 12, "#1c5cab"],
    [10 / 12, "#184f95"],
    [11 / 12, "#104281"],
    [12 / 12, "#0d366b"],
]

figura_mapa = px.choropleth(
    conteo_departamentos_mapa,
    geojson=geojson_departamentos,
    locations="departamento_codigo",
    # "featureidkey" le dice a Plotly en qué propiedad del GeoJSON
    # debe buscar el valor de "locations". Usamos el código DANE
    # (ej. "63") en vez del nombre, porque los nombres del GeoJSON
    # vienen en mayúsculas y sin tildes y son más difíciles de cruzar
    # sin errores que un código numérico exacto.
    featureidkey="properties.DPTO",
    color="personas",
    color_continuous_scale=ESCALA_AZUL_SECUENCIAL,
    hover_name="departamento",
    custom_data=["personas"],
)

# hovertemplate personalizado: nombre del departamento en negrita y la
# cantidad de personas debajo, sin la etiqueta técnica del código DANE.
figura_mapa.update_traces(
    hovertemplate="<b>%{hovertext}</b><br>%{customdata[0]:,} personas<extra></extra>",
    marker_line_color="#c3c2b7",  # borde fino y discreto entre departamentos
    marker_line_width=0.6,
)

# fitbounds="geojson" (y no "locations") para que siempre se vea el
# país completo, aunque los datos filtrados solo cubran una región.
figura_mapa.update_geos(fitbounds="geojson", visible=False, bgcolor="rgba(0,0,0,0)")
figura_mapa.update_layout(
    margin={"r": 0, "t": 10, "l": 0, "b": 0},
    height=600,
    # Fondo transparente para que el mapa se integre con el tema
    # (claro u oscuro) de Streamlit en vez de verse como un recuadro
    # blanco encima de la página.
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_family="system-ui, -apple-system, 'Segoe UI', sans-serif",
    coloraxis_colorbar=dict(title="Personas", ticks="outside"),
)
st.plotly_chart(figura_mapa, use_container_width=True, config={"displayModeBar": False})


# ---------------------------------------------------------------------------
# DETALLE DE BOGOTÁ D.C. POR LOCALIDAD
# ---------------------------------------------------------------------------
# Bogotá concentra la mayoría de inscritos, así que además del mapa por
# departamento mostramos un desglose por localidad (Chapinero, Suba,
# Kennedy, etc.). No usamos un mapa aquí porque las localidades son muy
# pequeñas para verse bien a la escala de un mapa de todo el país; una
# barra ordenada de mayor a menor es más fácil de leer para este caso.
conteo_localidades = agregar_por_localidad_bogota(df_filtrado)

if not conteo_localidades.empty:
    st.subheader("Detalle de Bogotá D.C. por localidad")
    st.caption(
        "Solo incluye a las personas de Bogotá que sí contestaron la pregunta "
        "de localidad en el formulario."
    )
    figura_localidades = px.bar(
        conteo_localidades,
        x="personas",
        y="localidad",
        orientation="h",
        color_discrete_sequence=["#2a78d6"],  # mismo azul que el mapa
        labels={"personas": "Personas", "localidad": "Localidad"},
    )
    # Ordena las barras de mayor a menor de arriba hacia abajo (por
    # defecto Plotly las pondría de menor a mayor de arriba hacia abajo).
    figura_localidades.update_layout(
        yaxis={"categoryorder": "total ascending"},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_family="system-ui, -apple-system, 'Segoe UI', sans-serif",
        margin={"r": 10, "t": 10, "l": 0, "b": 0},
        height=450,
    )
    figura_localidades.update_traces(hovertemplate="<b>%{y}</b><br>%{x:,} personas<extra></extra>")
    st.plotly_chart(figura_localidades, use_container_width=True, config={"displayModeBar": False})


# ---------------------------------------------------------------------------
# TABLA DE DETALLE POR MUNICIPIO
# ---------------------------------------------------------------------------
st.subheader("Detalle por municipio (de mayor a menor)")
st.dataframe(
    conteo_municipios.rename(
        columns={
            "municipio": "Municipio",
            "departamento": "Departamento",
            "departamento_codigo": "Código DANE",
            "personas": "Personas",
        }
    ),
    use_container_width=True,
    hide_index=True,
)


# ---------------------------------------------------------------------------
# VALORES QUE NO SE PUDIERON EMPAREJAR (para revisar a mano)
# ---------------------------------------------------------------------------
if not sin_emparejar.empty:
    with st.expander(
        f"⚠️ {len(sin_emparejar)} valor(es) de ciudad no se pudieron emparejar con confianza"
    ):
        st.caption(
            "Estos textos no se lograron asociar a ningún municipio oficial de Colombia "
            "con suficiente confianza. Puede tratarse de errores de digitación graves, "
            "nombres incompletos, o texto que no corresponde a un municipio."
        )
        st.dataframe(sin_emparejar, use_container_width=True, hide_index=True)
