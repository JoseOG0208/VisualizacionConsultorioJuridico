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

from data_loader import (
    RUTA_EXCEL_POR_DEFECTO,
    load_data,
    obtener_ruta_excel_disponible,
)
from procesamiento import (
    agregar_por_anio,
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

st.markdown(
    """
    <style>
        [data-testid="stAppViewContainer"] {
            background: #f6f9fe;
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #092450 0%, #0c326c 62%, #071a3d 100%);
        }
        [data-testid="stSidebar"] * {
            color: #f7fbff;
        }
        [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
            background: rgba(255, 255, 255, 0.08);
            border: 1px dashed rgba(255, 255, 255, 0.38);
        }
        .dashboard-brand {
            display: flex;
            align-items: center;
            gap: 14px;
            margin: 4px 0 28px;
        }
        .brand-mark {
            display: grid;
            place-items: center;
            width: 48px;
            height: 48px;
            border-radius: 14px;
            background: linear-gradient(145deg, #2188ff, #0b4eaf);
            box-shadow: 0 10px 24px rgba(18, 90, 188, 0.35);
            font-size: 25px;
        }
        .brand-title {
            color: white;
            font-size: 17px;
            line-height: 1.12;
            font-weight: 750;
        }
        .brand-subtitle {
            color: #a9c9f7;
            font-size: 11px;
            margin-top: 4px;
        }
        .hero-kicker {
            color: #2678da;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 4px;
        }
        .hero-title {
            color: #102a55;
            font-size: clamp(30px, 4vw, 48px);
            line-height: 1.04;
            font-weight: 800;
            margin: 0;
        }
        .hero-title span {
            color: #2b72ce;
            font-weight: 500;
        }
        .hero-copy {
            color: #5c7091;
            font-size: 15px;
            margin-top: 12px;
        }
        .section-heading {
            color: #122f5e;
            font-size: 24px;
            font-weight: 750;
            margin: 4px 0 12px;
        }
        .metric-card {
            min-height: 128px;
            padding: 20px 22px;
            border: 1px solid #d9e7fb;
            border-radius: 18px;
            background: linear-gradient(135deg, #ffffff, #f2f7ff);
            box-shadow: 0 10px 28px rgba(45, 91, 155, 0.08);
        }
        .metric-card.green {
            background: linear-gradient(135deg, #ffffff, #effcf7);
            border-color: #c5f0e1;
        }
        .metric-card.purple {
            background: linear-gradient(135deg, #ffffff, #f6f2ff);
            border-color: #e2d9ff;
        }
        .metric-label {
            color: #426083;
            font-size: 13px;
            font-weight: 650;
        }
        .metric-value {
            color: #102a55;
            font-size: 36px;
            line-height: 1.15;
            font-weight: 800;
            margin-top: 12px;
        }
        .metric-note {
            color: #0caa78;
            font-size: 12px;
            font-weight: 650;
            margin-top: 8px;
        }
        .map-shell {
            padding: 18px 22px 10px;
            border: 1px solid #d9e7fb;
            border-radius: 20px;
            background: rgba(255, 255, 255, 0.82);
            box-shadow: 0 12px 32px rgba(45, 91, 155, 0.08);
        }
        .rank-card {
            padding: 18px 18px 12px;
            border: 1px solid #d9e7fb;
            border-radius: 16px;
            background: #ffffff;
            box-shadow: 0 8px 22px rgba(45, 91, 155, 0.07);
        }
        .rank-title {
            color: #173b70;
            font-size: 17px;
            font-weight: 750;
            margin-bottom: 12px;
        }
        .rank-row {
            display: flex;
            align-items: center;
            gap: 9px;
            margin: 13px 0;
            color: #24456f;
            font-size: 13px;
            font-weight: 650;
        }
        .rank-number {
            display: grid;
            place-items: center;
            min-width: 24px;
            height: 24px;
            border-radius: 50%;
            color: white;
            background: #5598e7;
            font-size: 12px;
        }
        .rank-name { flex: 1; }
        .rank-value { color: #24456f; }
        .rank-bar {
            height: 7px;
            margin: -8px 0 10px 33px;
            border-radius: 99px;
            background: #e7eef9;
            overflow: hidden;
        }
        .rank-fill {
            height: 100%;
            border-radius: inherit;
            background: linear-gradient(90deg, #4e9af3, #124eb5);
        }
        div[data-testid="stPlotlyChart"] {
            border-radius: 16px;
        }
    </style>
    """,
    unsafe_allow_html=True,
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
ruta_excel_a_usar = (
    archivo_subido
    if archivo_subido is not None
    else obtener_ruta_excel_disponible()
)

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
# ENCABEZADO Y FILTROS
# ---------------------------------------------------------------------------
st.sidebar.markdown(
    """
    <div class="dashboard-brand">
        <div class="brand-mark">⚖</div>
        <div>
            <div class="brand-title">Consultorio Contable<br>Javeriano</div>
            <div class="brand-subtitle">Panel de participación</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown('<div class="hero-kicker">Participación territorial</div>', unsafe_allow_html=True)
st.markdown(
    '<h1 class="hero-title">Mapa de participación<br><span>Consultorio Contable Javeriano</span></h1>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="hero-copy">Personas inscritas a las capacitaciones, por ciudad, municipio y departamento de Colombia.</div>',
    unsafe_allow_html=True,
)
st.write("")

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
conteo_anios = agregar_por_anio(df_filtrado)

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
with col_m1:
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">Personas inscritas</div><div class="metric-value">{total_personas:,}</div><div class="metric-note">↗ Filtro actual</div></div>',
        unsafe_allow_html=True,
    )
with col_m2:
    porcentaje_ubicado = total_con_ubicacion / max(total_personas, 1) * 100
    st.markdown(
        f'<div class="metric-card green"><div class="metric-label">Con ciudad/departamento identificado</div><div class="metric-value">{int(total_con_ubicacion):,}</div><div class="metric-note">↗ {porcentaje_ubicado:.1f}% del total</div></div>',
        unsafe_allow_html=True,
    )
with col_m3:
    st.markdown(
        f'<div class="metric-card purple"><div class="metric-label">Municipios distintos representados</div><div class="metric-value">{total_municipios_distintos:,}</div><div class="metric-note">↗ Cobertura territorial</div></div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# MAPA COROPLÉTICO POR DEPARTAMENTO
# ---------------------------------------------------------------------------
st.markdown('<div class="section-heading">Mapa por departamento</div>', unsafe_allow_html=True)

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

# La escala separa claramente departamentos sin registros de los que tienen
# actividad. El tramo naranja/rojo permite detectar rápidamente las mayores
# concentraciones sin perder los valores intermedios.
maximo_personas = max(int(conteo_departamentos_mapa["personas"].max()), 1)
conteo_departamentos_mapa["porcentaje_total"] = (
    conteo_departamentos_mapa["personas"] / max(int(total_con_ubicacion), 1) * 100
).round(1)
conteo_departamentos_mapa["posicion_ranking"] = (
    conteo_departamentos_mapa["personas"].rank(method="min", ascending=False).astype(int)
)
ESCALA_DEPARTAMENTOS = [
    [0.0, "#e5e7eb"],
    [0.001, "#dbeafe"],
    [0.25, "#93c5fd"],
    [0.50, "#3b82f6"],
    [0.75, "#f59e0b"],
    [0.90, "#ea580c"],
    [1.0, "#b91c1c"],
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
    color_continuous_scale=ESCALA_DEPARTAMENTOS,
    hover_name="departamento",
    custom_data=["personas", "porcentaje_total", "posicion_ranking"],
)

# hovertemplate personalizado: nombre del departamento en negrita y la
# cantidad de personas debajo, sin la etiqueta técnica del código DANE.
figura_mapa.update_traces(
    hovertemplate=(
        "<b>%{hovertext}</b><br>"
        "%{customdata[0]:,} personas<br>"
        "%{customdata[1]:.1f}% del total ubicado<br>"
        "Puesto nacional: %{customdata[2]}<extra></extra>"
    ),
    marker_line_color="#ffffff",
    marker_line_width=1.2,
)

# fitbounds="geojson" (y no "locations") para que siempre se vea el
# país completo, aunque los datos filtrados solo cubran una región.
figura_mapa.update_geos(
    fitbounds="geojson",
    visible=False,
    bgcolor="rgba(0,0,0,0)",
    showcoastlines=True,
    coastlinecolor="#64748b",
)
figura_mapa.update_layout(
    margin={"r": 0, "t": 10, "l": 0, "b": 0},
    height=700,
    # Fondo transparente para que el mapa se integre con el tema
    # (claro u oscuro) de Streamlit en vez de verse como un recuadro
    # blanco encima de la página.
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_family="system-ui, -apple-system, 'Segoe UI', sans-serif",
    coloraxis=dict(cmin=0, cmax=maximo_personas),
    coloraxis_colorbar=dict(title="Personas", ticks="outside", thickness=18),
)

col_ranking, col_mapa = st.columns([0.28, 0.72], gap="large")
with col_ranking:
    st.markdown('<div class="rank-card"><div class="rank-title">Top 5 departamentos</div>', unsafe_allow_html=True)
    top_departamentos = conteo_departamentos_mapa.sort_values("personas", ascending=False).head(5)
    maximo_top = max(int(top_departamentos["personas"].max()), 1)
    for posicion, (_, fila) in enumerate(top_departamentos.iterrows(), start=1):
        ancho = int(fila["personas"] / maximo_top * 100)
        st.markdown(
            f'<div class="rank-row"><span class="rank-number">{posicion}</span><span class="rank-name">{fila["departamento"]}</span><span class="rank-value">{int(fila["personas"]):,}</span></div><div class="rank-bar"><div class="rank-fill" style="width: {ancho}%"></div></div>',
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)
with col_mapa:
    st.markdown('<div class="map-shell">', unsafe_allow_html=True)
    st.plotly_chart(figura_mapa, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# EVOLUCIÓN ANUAL
# ---------------------------------------------------------------------------
st.subheader("Personas atendidas por año")
st.caption(
    "Conteo de inscripciones depuradas según el año de la fecha de inicio "
    "registrada en el formulario."
)

if conteo_anios.empty:
    st.info("No hay fechas válidas para construir el gráfico anual con el filtro actual.")
else:
    figura_anual = px.bar(
        conteo_anios,
        x="anio",
        y="personas",
        text="personas",
        labels={"anio": "Año", "personas": "Personas"},
        color="personas",
        color_continuous_scale=[[0, "#93c5fd"], [1, "#1d4ed8"]],
    )
    figura_anual.update_traces(
        texttemplate="%{text:,}",
        textposition="outside",
        cliponaxis=False,
        hovertemplate="Año %{x}<br><b>%{y:,} personas</b><extra></extra>",
    )
    figura_anual.update_layout(
        height=420,
        margin={"r": 20, "t": 20, "l": 10, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_family="system-ui, -apple-system, 'Segoe UI', sans-serif",
        showlegend=False,
        coloraxis_showscale=False,
        yaxis={"title": "Personas", "rangemode": "tozero", "showgrid": True, "gridcolor": "#e2e8f0"},
        xaxis={"title": "Año", "dtick": 1},
    )
    st.plotly_chart(figura_anual, use_container_width=True, config={"displayModeBar": False})


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
