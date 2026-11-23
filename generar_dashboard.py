"""
generar_dashboard.py
--------------------
Lee los controles semanales de la base de datos «Seguimiento del peso» de Notion
y genera una página HTML (docs/index.html) con el dashboard.

Uso:
    # Con datos reales (necesita las variables de entorno NOTION_TOKEN y NOTION_DATABASE_ID)
    python generar_dashboard.py

    # Sin conexión, con un JSON de prueba (útil para trastear con el diseño)
    python generar_dashboard.py --desde-json datos_prueba.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# 1. Configuración
# ---------------------------------------------------------------------------

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"  # versión estable de la API; la fijamos para que nada cambie sin avisar

# Nombre de la propiedad en Notion  ->  nombre corto que usaremos en el HTML
COLUMNAS = {
    "Registro": "registro",
    "Fecha": "fecha",
    "Peso (kg)": "peso",
    "IMC": "imc",
    "Grasa corporal (%)": "grasa",
    "Grasa visceral": "visceral",
    "Masa muscular (kg)": "muscular",
    "Agua corporal (%)": "agua",
    "Proteína (%)": "proteina",
    "Metabolismo basal (kcal/día)": "metab",
    "Cintura (cm)": "cintura",
    "Cadera (cm)": "cadera",
    "Pecho (cm)": "pecho",
    "Brazo (cm)": "brazo",
    "Muslo (cm)": "muslo",
    "Notas": "notas",
}

CARPETA = Path(__file__).parent
PLANTILLA = CARPETA / "plantilla.html"
MARCADOR = "/*__DATOS__*/null"  # trozo de la plantilla que sustituimos por los datos


# ---------------------------------------------------------------------------
# 2. Leer de Notion
# ---------------------------------------------------------------------------

def leer_paginas_notion(token: str, database_id: str) -> list[dict]:
    """Devuelve todas las páginas (filas) de la base de datos, ordenadas por Fecha.

    La API de Notion devuelve como mucho 100 filas por llamada. Si hay más,
    la respuesta trae has_more=True y un next_cursor para pedir la siguiente tanda.
    """
    url = f"{NOTION_API}/databases/{database_id}/query"
    cabeceras = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    cuerpo = {"sorts": [{"property": "Fecha", "direction": "ascending"}], "page_size": 100}

    paginas = []
    while True:
        r = requests.post(url, headers=cabeceras, json=cuerpo, timeout=30)
        r.raise_for_status()  # si Notion responde con error (401, 404…) paramos aquí
        datos = r.json()
        paginas.extend(datos["results"])
        if not datos.get("has_more"):
            break
        cuerpo["start_cursor"] = datos["next_cursor"]
    return paginas


def valor_propiedad(prop: dict):
    """Convierte una propiedad de Notion en un valor simple de Python.

    Cada propiedad viene como {"type": "number", "number": 125.8}, o
    {"type": "title", "title": [{"plain_text": "Control 01"}, ...]}, etc.
    """
    tipo = prop.get("type")
    if tipo == "number":
        return prop["number"]
    if tipo in ("title", "rich_text"):
        texto = "".join(trozo["plain_text"] for trozo in prop[tipo])
        return texto or None
    if tipo == "date":
        return prop["date"]["start"][:10] if prop["date"] else None
    return None  # tipos que no usamos (archivos, etc.)


def simplificar(pagina: dict) -> dict:
    """Pasa una página de Notion a un diccionario plano con los nombres cortos."""
    props = pagina["properties"]
    fila = {corto: valor_propiedad(props[largo]) for largo, corto in COLUMNAS.items() if largo in props}
    fila["url"] = pagina.get("url")
    return fila


# ---------------------------------------------------------------------------
# 3. Generar el HTML
# ---------------------------------------------------------------------------

def generar_html(controles: list[dict], salida: Path) -> None:
    """Mete los datos en la plantilla y escribe el HTML final."""
    plantilla = PLANTILLA.read_text(encoding="utf-8")
    if MARCADOR not in plantilla:
        sys.exit(f"No encuentro el marcador {MARCADOR!r} en {PLANTILLA.name}")

    datos = {
        "generado": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "controles": [c for c in controles if c.get("fecha")],  # sin fecha no se puede pintar
    }
    # ensure_ascii=False mantiene las tildes legibles; "</" se escapa para no cerrar el <script> por error
    json_datos = json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")

    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(plantilla.replace(MARCADOR, json_datos), encoding="utf-8")
    print(f"✔ {len(datos['controles'])} controles → {salida}")


# ---------------------------------------------------------------------------
# 4. Programa principal
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Genera el dashboard de seguimiento del peso")
    parser.add_argument("--desde-json", type=Path, help="usar un JSON local en vez de Notion")
    parser.add_argument("--salida", type=Path, default=CARPETA / "docs" / "index.html")
    args = parser.parse_args()

    if args.desde_json:
        controles = json.loads(args.desde_json.read_text(encoding="utf-8"))
    else:
        token = os.environ.get("NOTION_TOKEN")
        database_id = os.environ.get("NOTION_DATABASE_ID")
        if not token or not database_id:
            sys.exit("Faltan las variables de entorno NOTION_TOKEN y/o NOTION_DATABASE_ID")
        controles = [simplificar(p) for p in leer_paginas_notion(token, database_id)]

    generar_html(controles, args.salida)


if __name__ == "__main__":
    main()
