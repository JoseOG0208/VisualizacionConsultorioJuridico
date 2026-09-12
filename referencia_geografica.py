"""
referencia_geografica.py
=========================
Este archivo carga la información "oficial" que usamos como referencia
para saber qué municipios existen en Colombia y a qué departamento
pertenece cada uno (basado en la codificación DIVIPOLA del DANE), y
también carga el mapa (GeoJSON) con los polígonos de los 33
departamentos que se usa para dibujar el mapa coroplético.

Archivos que usa (carpeta reference/):
- municipios_colombia_divipola.csv: tabla oficial municipio -> departamento.
- colombia_departamentos.geojson: polígonos de los 33 departamentos
  (incluye Bogotá D.C. como una unidad más, tal como lo maneja el DANE).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd

from data_loader import normalizar_texto

RUTA_CSV_MUNICIPIOS = "reference/municipios_colombia_divipola.csv"
RUTA_GEOJSON_DEPARTAMENTOS = "reference/colombia_departamentos.geojson"


@dataclass(frozen=True)
class Municipio:
    """Un municipio de la tabla oficial, con su nombre ya normalizado
    (mayúsculas, sin tildes) para poder compararlo con lo que escribió
    la gente en el formulario.
    """

    nombre_normalizado: str
    nombre: str
    departamento: str
    departamento_codigo: str  # código DANE del departamento, 2 dígitos, ej "63"
    municipio_codigo: str  # código DANE del municipio, 5 dígitos, ej "63001"

    @property
    def es_capital_de_departamento(self) -> bool:
        """En DIVIPOLA, el código del municipio capital siempre termina
        en "001" (ej: Armenia = 63001 es la capital de Quindío = 63).
        Esta propiedad nos sirve más adelante para "desempatar" cuando
        dos municipios de distintos departamentos tienen el mismo
        nombre (por ejemplo, existe un "Armenia" en Antioquia y otro
        en Quindío: si alguien solo escribe "Armenia" sin aclarar más,
        asumimos que se refiere a la capital, que es la más conocida).
        """
        return self.municipio_codigo.endswith("001")


# Alias cortos que la gente suele escribir en vez del nombre oficial
# completo del departamento.
ALIAS_DEPARTAMENTOS = {
    "VALLE": "VALLE DEL CAUCA",
    "GUAJIRA": "LA GUAJIRA",
    "SAN ANDRES": "ARCHIPIELAGO DE SAN ANDRES PROVIDENCIA Y SANTA CATALINA",
}


def cargar_municipios(ruta_csv: str = RUTA_CSV_MUNICIPIOS) -> list[Municipio]:
    """Carga la tabla oficial de municipios de Colombia (DIVIPOLA)."""
    df = pd.read_csv(ruta_csv, dtype=str)
    municipios = []
    for _, fila in df.iterrows():
        depto_codigo = fila["CÓDIGO DANE DEL DEPARTAMENTO"].strip().zfill(2)
        muni_codigo = fila["CÓDIGO DANE DEL MUNICIPIO"].strip().zfill(5)
        municipios.append(
            Municipio(
                nombre_normalizado=normalizar_texto(fila["MUNICIPIO"]),
                nombre=fila["MUNICIPIO"].strip(),
                departamento=fila["DEPARTAMENTO"].strip(),
                departamento_codigo=depto_codigo,
                municipio_codigo=muni_codigo,
            )
        )
    return municipios


def construir_indice_departamentos(municipios: list[Municipio]) -> dict[str, tuple[str, str]]:
    """Devuelve un diccionario {NOMBRE_DEPTO_NORMALIZADO: (nombre_oficial, codigo)}.

    Se usa para detectar cuándo el texto escrito por una persona
    menciona el nombre de un departamento (por ejemplo "Calarca-Quindio"
    menciona a "Quindío").
    """
    indice: dict[str, tuple[str, str]] = {}
    for m in municipios:
        indice[normalizar_texto(m.departamento)] = (m.departamento, m.departamento_codigo)
    return indice


def listar_todos_los_departamentos(municipios: list[Municipio]) -> pd.DataFrame:
    """Devuelve una tabla con los 33 departamentos de Colombia (nombre
    oficial + código DANE), sin duplicados. Se usa para que el mapa
    siempre muestre el país completo, incluso los departamentos que
    todavía no tienen ninguna persona inscrita (esos se ven en 0).
    """
    filas = {(m.departamento, m.departamento_codigo) for m in municipios}
    return pd.DataFrame(sorted(filas), columns=["departamento", "departamento_codigo"])


def cargar_geojson_departamentos(ruta: str = RUTA_GEOJSON_DEPARTAMENTOS) -> dict:
    """Carga el archivo GeoJSON con los polígonos de los departamentos.

    Cada "feature" del GeoJSON trae la propiedad "DPTO", que es el
    código DANE del departamento (ej: "63" para Quindío) escrito con
    2 dígitos como texto. Usamos ese código -y no el nombre- para
    cruzar los datos con nuestra tabla de conteos, porque los nombres
    en el GeoJSON vienen en mayúsculas y sin tildes (ej "SANTAFE DE
    BOGOTA D.C" en vez de "Bogotá D.C."), mientras que los códigos
    numéricos son exactos y no tienen ese problema.
    """
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)
