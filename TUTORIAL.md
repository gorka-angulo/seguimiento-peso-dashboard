# Tutorial: dashboard del peso en Notion (Python + GitHub Actions + GitHub Pages)

## 1. Qué vamos a montar

```
Notion (base "Seguimiento del peso")
        │  la API de Notion (token secreto)
        ▼
generar_dashboard.py  ──►  docs/index.html   (plantilla.html + tus datos)
        ▲                          │
GitHub Actions (cada día)          ▼
                           GitHub Pages  ──►  bloque /embed en Notion
```

1. Cada día, **GitHub Actions** (un ordenador de GitHub) ejecuta el script de Python.
2. El script pide a la **API de Notion** todos tus controles semanales.
3. Mete esos datos dentro de `plantilla.html` y genera `docs/index.html`.
4. GitHub publica ese HTML en **GitHub Pages**, con una URL fija.
5. En Notion pegas esa URL en un bloque **Embed**, y el dashboard aparece dentro de tu página.

La página que se publica es estática: es HTML con los datos ya metidos dentro. El navegador no necesita el token de Notion para nada, y el token nunca sale de GitHub.

## 2. Archivos del proyecto

| Archivo | Para qué sirve |
|---|---|
| `generar_dashboard.py` | Lee Notion y genera el HTML |
| `plantilla.html` | Diseño del dashboard: CSS, y JavaScript que dibuja tarjetas, gráfico y tabla |
| `requirements.txt` | Librerías de Python necesarias (solo `requests`) |
| `.github/workflows/actualizar-dashboard.yml` | La "receta" que GitHub ejecuta cada día |
| `.gitignore` | Archivos que no se suben a GitHub (`docs/`, `.env`…) |

## 3. Paso a paso para ponerlo en marcha

### 3.1 Crear la integración de Notion (el token)

1. Ve a <https://www.notion.so/profile/integrations>, pulsa **Nueva integración** y elige tipo **Interna**. Ponle un nombre, por ejemplo "Dashboard peso".
2. Copia el **token secreto** (empieza por `ntn_`). Es una contraseña: no lo pegues en el código.
3. Abre la base **Seguimiento del peso** en Notion. Pulsa `···` (arriba a la derecha), luego **Conexiones**, y añade la integración "Dashboard peso". Si no haces esto, la API responderá `404 object_not_found`.

El **ID de la base** es el trozo de 32 caracteres de su URL. El de la tuya es:

```
dd7383843db683b1853401c801eef887
```

### 3.2 Probarlo en tu PC (PowerShell)

```powershell
cd ruta\a\seguimiento-peso-dashboard
pip install -r requirements.txt
$env:NOTION_TOKEN = "ntn_xxx..."
$env:NOTION_DATABASE_ID = "dd7383843db683b1853401c801eef887"
python generar_dashboard.py
start docs\index.html
```

En WSL/Linux sería `export NOTION_TOKEN=...` y luego `xdg-open docs/index.html`.

### 3.3 Subirlo a GitHub

1. Crea un repositorio nuevo, por ejemplo `fit-road-dashboard`, y sube estos archivos (`git init`, `git add .`, `git commit`, `git push`).
2. En el repo, ve a **Settings → Secrets and variables → Actions → New repository secret** y crea dos secretos:
   - `NOTION_TOKEN` con tu token.
   - `NOTION_DATABASE_ID` con `dd7383843db683b1853401c801eef887`.
3. En **Settings → Pages → Build and deployment → Source**, elige **GitHub Actions**.
4. En la pestaña **Actions**, abre "Actualizar dashboard" y pulsa **Run workflow**.
5. Cuando termine, tendrás la web en `https://TU-USUARIO.github.io/fit-road-dashboard/`.

### 3.4 Incrustarlo en Notion

En tu página de The Fit Road escribe `/embed`, pega la URL de GitHub Pages y ajusta el alto del bloque (unos 1100 px). Si cambias el ancho del bloque, el gráfico se redibuja solo.

### 3.5 Privacidad: léelo antes

- Con una cuenta gratuita, GitHub Pages **solo funciona con repos públicos**, y la web publicada **es pública**: la ve cualquiera que tenga la URL.
- El token sí está a salvo, porque es un *secret* y no aparece en el código. Los que quedan expuestos son tus datos de peso y medidas.
- La plantilla lleva `<meta name="robots" content="noindex">` para que Google no la indexe, pero eso no la hace privada.
- Alternativas si no te convence: servir `docs/index.html` desde tu servidor de casa (un `nginx` en Docker con un cron que ejecute el script), o pagar GitHub Pro para tener Pages en un repo privado. Aun así, la web seguiría siendo accesible para quien tenga la URL.

## 4. Cómo funciona el código de Python

### 4.1 Configuración

```python
NOTION_VERSION = "2022-06-28"
COLUMNAS = {"Peso (kg)": "peso", "Grasa corporal (%)": "grasa", ...}
```

- La API de Notion exige la cabecera `Notion-Version`. La fijamos para que un cambio de Notion no rompa el script.
- `COLUMNAS` traduce el nombre de cada propiedad de Notion a un nombre corto. Si añades una propiedad nueva a la base, añádela aquí y en `MEDIDAS` de la plantilla.

### 4.2 Pedir los datos: `leer_paginas_notion`

```python
r = requests.post(url, headers=cabeceras, json=cuerpo, timeout=30)
r.raise_for_status()
```

- Es un `POST` a `/v1/databases/{id}/query`. Le pasamos el orden en el `json=cuerpo` (`sorts` por Fecha ascendente).
- `raise_for_status()` lanza una excepción si Notion responde con error. Así el workflow falla en rojo en vez de publicar un dashboard vacío.
- **Paginación**: Notion devuelve como mucho 100 filas por llamada. Por eso el bucle `while True` repite la petición con `start_cursor` mientras `has_more` sea `True`. Es un patrón muy típico en APIs y conviene que te lo aprendas.

### 4.3 Aplanar cada fila: `valor_propiedad` y `simplificar`

Notion devuelve cada propiedad envuelta en su tipo:

```json
"Peso (kg)": {"type": "number", "number": 125.8}
"Registro":  {"type": "title", "title": [{"plain_text": "Control semanal 01"}]}
"Fecha":     {"type": "date", "date": {"start": "2026-11-23", "end": null}}
```

- `valor_propiedad` mira el `type` y saca el valor. En los textos une los trozos con `"".join(...)`; en las fechas se queda con los 10 primeros caracteres (`AAAA-MM-DD`).
- `simplificar` usa una *dict comprehension* para recorrer `COLUMNAS` y construir `{"peso": 125.8, "fecha": "2026-11-23", ...}`.

### 4.4 Generar el HTML: `generar_html`

La plantilla contiene esta línea:

```js
const DATOS = /*__DATOS__*/null;
```

Python sustituye `/*__DATOS__*/null` por el JSON con los datos (`str.replace`). Hay dos detalles:

- Si abres la plantilla tal cual, sigue siendo JavaScript válido (`DATOS = null`). Así puedes ver el diseño vacío sin ejecutar nada.
- `.replace("</", "<\\/")` evita que un texto como `</script>` en tus notas cierre la etiqueta `<script>` por accidente.

### 4.5 `main` y `argparse`

`--desde-json archivo.json` te deja generar el dashboard sin Notion, con datos de prueba. Sirve para trastear con el diseño. El archivo debe ser una lista de filas ya simplificadas:

```json
[{"registro": "Prueba", "fecha": "2026-11-23", "peso": 125.8, "grasa": 38.3}]
```

```bash
python generar_dashboard.py --desde-json prueba.json --salida prueba.html
```

## 5. Cómo funciona el JavaScript de la plantilla

Está dividido en 8 bloques numerados. Lo importante de cada uno:

1. **DATOS**: el hueco que rellena Python.
2. **MEDIDAS**: la configuración de cada medida. `band` es el rango saludable que se pinta en verde. `better` indica si bajar es bueno (`-1`) o malo (`1`), y de eso depende el color verde/rojo de los cambios. El rango del peso se calcula con un IMC de 18,5–24,9 y `ALTURA_CM`.
3. **Utilidades**: `fmt` formatea con coma decimal (`toLocaleString('es-ES')`). `el()` y `svgEl()` son atajos para crear elementos sin usar `innerHTML`, que es más seguro.
4. **Frase de resumen**: tiene dos versiones, una para un solo control y otra para varios.
5. **Tarjetas**: `cambios(m)` calcula el último valor, la diferencia con el anterior y con el primero.
6. **Gráfico SVG hecho a mano, sin librerías**. La clave son las **escalas**, que convierten un dato en un píxel:
   ```js
   const x = (d) => m.l + (d - x0) / (x1 - x0) * (W - m.l - m.r);
   const y = (v) => H - m.b - (v - lo) / (hi - lo) * (H - m.t - m.b);
   ```
   Es una regla de tres: dónde cae `d` entre `x0` y `x1`, llevado al ancho disponible. En la `y` se resta desde abajo porque en SVG la coordenada 0 está arriba. `pasoBonito` elige marcas "redondas" para el eje (1, 2, 5, 10…). El tooltip busca el punto más cercano al ratón con un `reduce`.
7. **Tabla**: muestra los controles del más reciente al más antiguo (`slice().reverse()`; el `slice()` hace una copia para no alterar el original).
8. **Arranque**: rellena el desplegable, pinta todo y redibuja el gráfico al cambiar de tamaño, con un pequeño retraso para no redibujar 100 veces seguidas.

## 6. El workflow de GitHub Actions

```yaml
on:
  schedule:
    - cron: "17 5 * * *"   # minuto hora día mes día_semana (UTC)
  workflow_dispatch:        # botón manual
  push:
    branches: [main]        # al subir cambios
```

Pasos: descarga el código, instala Python, instala `requests`, ejecuta el script con los secretos como variables de entorno (`${{ secrets.NOTION_TOKEN }}`), y publica la carpeta `docs` con `upload-pages-artifact` + `deploy-pages`.

`docs/` está en `.gitignore` porque el HTML se genera en GitHub y no hace falta subirlo al repositorio.

## 7. Problemas típicos

| Síntoma | Causa probable |
|---|---|
| `401 unauthorized` | Token mal copiado o secreto mal nombrado |
| `404 object_not_found` | No has añadido la integración en *Conexiones* de la base, o el ID está mal |
| El workflow va bien pero la web no cambia | Pages no está en **Source: GitHub Actions**, o la caché del navegador. Prueba con Ctrl+F5 |
| Notion no muestra el embed | Comprueba que la URL abre en el navegador. Usa `/embed`, no un enlace normal |
| Falta una medida en el gráfico | El nombre en `COLUMNAS` no coincide exactamente con el de la propiedad en Notion (tildes, paréntesis…) |

## 8. Ejercicios para practicar

1. Añade una tarjeta de **Masa muscular**: pon `tile: true` en `MEDIDAS.muscular`.
2. Añade al gráfico una **línea de objetivo** (por ejemplo, 110 kg) con un `svgEl('line', ...)` discontinuo (`'stroke-dasharray': '4 4'`).
3. En Python, calcula la **media de pérdida semanal** y pásala dentro de `datos` para mostrarla en la frase de resumen.
4. Cambia el cron para que se ejecute solo los lunes: `"17 5 * * 1"`.
