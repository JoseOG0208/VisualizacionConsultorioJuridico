"""
emparejamiento_municipios.py
==============================
Aquí vive la lógica de "coincidencia aproximada" (fuzzy matching):
recibe el texto libre que la gente escribió en el formulario (ej.
"Calarca-Quindio", "ARMENIA", "Facatativa cundinamarca") y trata de
adivinar a cuál municipio OFICIAL de Colombia corresponde, usando la
librería rapidfuzz para medir qué tan "parecidas" son dos palabras.

Estrategia (explicada en simple):
1. Buscamos si el texto menciona el nombre de un DEPARTAMENTO
   (ej. "Quindio", "Cundinamarca"). Si lo encontramos, lo separamos
   del resto del texto: eso nos da una "pista" de en qué departamento
   buscar, y reduce muchísimo el riesgo de confundir municipios que
   se llaman igual pero quedan en departamentos distintos
   (por ejemplo, existe un "Armenia" en Antioquia y otro en Quindío).
2. Con esa pista (o sin ella, si no se encontró ninguna), comparamos
   el texto restante contra la lista de municipios usando rapidfuzz,
   y nos quedamos con el más parecido, siempre que la similitud sea
   suficientemente alta (score >= UMBRAL_CONFIANZA).
3. Si dos municipios distintos (de distintos departamentos) tienen
   exactamente el mismo nombre, preferimos el que es "capital de
   departamento" (ver Municipio.es_capital_de_departamento), porque
   suele ser el más conocido y el más probable si alguien no
   especificó el departamento.
4. Si no logramos un emparejamiento confiable, devolvemos un
   resultado "sin match" para que quede en la lista de valores a
   revisar a mano.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz, process

from data_loader import normalizar_texto
from referencia_geografica import ALIAS_DEPARTAMENTOS, Municipio

# Por debajo de este puntaje (0-100) no confiamos en el emparejamiento.
# Se eligió 82 probando contra datos reales: separa bien los casos
# correctos (mayoría en 90-100) de los errores de digitación graves.
UMBRAL_CONFIANZA = 82


@dataclass
class ResultadoEmparejamiento:
    municipio: str | None
    departamento: str | None
    departamento_codigo: str | None
    score: float | None
    estado: str  # "ok" | "solo_departamento" | "sin_match" | "vacio"


def _buscar_pista_de_departamento(
    texto_normalizado: str, indice_departamentos: dict[str, tuple[str, str]]
) -> tuple[tuple[str, str] | None, str]:
    """Busca si el texto menciona un departamento y, si lo encuentra,
    lo quita del texto para dejar solo la posible parte del municipio.

    Si el texto menciona más de un departamento (caso raro, pero
    ocurre, ej. "Cordoba Quindio"), nos quedamos con el que aparece
    MÁS AL FINAL del texto, porque el patrón típico en el formulario
    es "municipio, departamento" (el departamento va al final).
    """
    nombres_posibles = sorted(
        set(list(indice_departamentos.keys()) + list(ALIAS_DEPARTAMENTOS.keys())),
        key=len,
        reverse=True,
    )

    mejor_coincidencia = None  # (posicion_inicio, nombre_real, codigo)
    for nombre_buscado in nombres_posibles:
        patron = r"\b" + re.escape(nombre_buscado) + r"\b"
        coincidencia = None
        for m in re.finditer(patron, texto_normalizado):
            coincidencia = m  # nos quedamos con la última ocurrencia de este nombre
        if coincidencia is None:
            continue
        nombre_real = ALIAS_DEPARTAMENTOS.get(nombre_buscado, nombre_buscado)
        if nombre_real not in indice_departamentos:
            continue
        if mejor_coincidencia is None or coincidencia.start() > mejor_coincidencia[0]:
            mejor_coincidencia = (coincidencia.start(), nombre_buscado, nombre_real)

    if mejor_coincidencia is None:
        return None, texto_normalizado

    _, nombre_buscado, nombre_real = mejor_coincidencia
    patron = r"\b" + re.escape(nombre_buscado) + r"\b"
    resto = re.sub(patron, " ", texto_normalizado)
    resto = re.sub(r"\s+", " ", resto).strip(" -,/")
    return indice_departamentos[nombre_real], resto


def _mejor_match_en(texto: str, candidatos: list[Municipio]):
    """Envoltorio sobre rapidfuzz: busca el municipio más parecido a
    `texto` dentro de la lista `candidatos`. Devuelve (score, [Municipio,...])
    con todos los municipios que comparten el nombre ganador (por si
    hay más de uno, para poder desempatar después).
    """
    if not texto or not candidatos:
        return None
    nombres = [m.nombre_normalizado for m in candidatos]
    resultado = process.extractOne(texto, nombres, scorer=fuzz.WRatio)
    if resultado is None:
        return None
    nombre_ganador, score, _ = resultado
    empatados = [m for m in candidatos if m.nombre_normalizado == nombre_ganador]
    return score, empatados


def _desempatar(candidatos: list[Municipio]) -> Municipio:
    """Si varios municipios comparten nombre, preferimos la capital de
    departamento (ver docstring de Municipio.es_capital_de_departamento).
    Si ninguno es capital, simplemente nos quedamos con el primero.
    """
    if len(candidatos) == 1:
        return candidatos[0]
    capitales = [m for m in candidatos if m.es_capital_de_departamento]
    return capitales[0] if capitales else candidatos[0]


def emparejar_ciudad(
    texto_original: object,
    municipios: list[Municipio],
    indice_departamentos: dict[str, tuple[str, str]],
) -> ResultadoEmparejamiento:
    """Función principal: recibe el texto libre de "ciudad/municipio"
    del formulario y devuelve el municipio + departamento oficiales,
    o un estado indicando que no se pudo emparejar con confianza.
    """
    texto = normalizar_texto(texto_original)
    if not texto:
        return ResultadoEmparejamiento(None, None, None, None, "vacio")

    pista_departamento, resto = _buscar_pista_de_departamento(texto, indice_departamentos)

    if pista_departamento is not None:
        nombre_depto, codigo_depto = pista_departamento
        candidatos = [m for m in municipios if m.departamento_codigo == codigo_depto]

        opciones = []
        if len(resto) >= 3:
            r = _mejor_match_en(resto, candidatos)
            if r:
                opciones.append(r)
        r_completo = _mejor_match_en(texto, candidatos)
        if r_completo:
            opciones.append(r_completo)

        mejor = max(opciones, key=lambda o: o[0], default=None)

        if mejor is None or mejor[0] < UMBRAL_CONFIANZA:
            # No encontramos un municipio confiable dentro de ese
            # departamento, pero SÍ sabemos el departamento: lo dejamos
            # marcado como "sin especificar" en vez de descartarlo del
            # todo, para no perder la información parcial que sí tenemos.
            return ResultadoEmparejamiento(
                municipio=f"Sin especificar ({nombre_depto})",
                departamento=nombre_depto,
                departamento_codigo=codigo_depto,
                score=mejor[0] if mejor else None,
                estado="solo_departamento",
            )

        elegido = _desempatar(mejor[1])
        return ResultadoEmparejamiento(
            municipio=elegido.nombre,
            departamento=elegido.departamento,
            departamento_codigo=elegido.departamento_codigo,
            score=mejor[0],
            estado="ok",
        )

    # No se detectó ningún departamento mencionado: buscamos en TODO el país.
    resultado = _mejor_match_en(texto, municipios)
    if resultado is None or resultado[0] < UMBRAL_CONFIANZA:
        return ResultadoEmparejamiento(
            None, None, None, resultado[0] if resultado else None, "sin_match"
        )

    elegido = _desempatar(resultado[1])
    return ResultadoEmparejamiento(
        municipio=elegido.nombre,
        departamento=elegido.departamento,
        departamento_codigo=elegido.departamento_codigo,
        score=resultado[0],
        estado="ok",
    )
