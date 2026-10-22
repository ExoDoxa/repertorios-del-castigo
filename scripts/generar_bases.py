"""Genera las tres bases armonizadas a partir de los CSV crudos exportados por la extensión.

    python scripts/generar_bases.py [--datos datos/bases_armonizadas]

La carpeta de datos debe contener Facebook_Instagram/crudos/ y TikTok/crudos/ (ver datos/README.md).

Pasos:
  1. Pasa Facebook_Instagram/crudos/ y TikTok/crudos/ por build_corpus.py (en esta misma carpeta),
     cada uno a un directorio temporal.
  2. Escribe, con las mismas columnas en las tres:
       Facebook_Instagram/base_armonizada_FB_IG_2026-10-21.xlsx
       TikTok/base_armonizada_TikTok_2026-10-21.xlsx
       base_armonizada_FB_IG_TikTok_2026-10-21.xlsx          (las tres plataformas juntas)
  3. Escribe inventario_publicaciones.csv en cada subcarpeta (un renglón por publicación).

Requiere Python 3.10+ y openpyxl. build_corpus.py es solo librería estándar.
"""
import argparse
import csv
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

AQUI = Path(__file__).resolve().parent
FECHA = "2026-10-21"

COLUMNAS = [
    ("Plataforma", "Facebook, Instagram o TikTok."),
    ("Tipo_Elemento", "Comentario o Respuesta según la plataforma. En Facebook las respuestas son INFERIDAS: mirar Nivel_Comentario."),
    ("ID_Post_Origen", "Identificador de la publicación (Instagram: shortcode; Facebook: id o pfbid; TikTok: id del video)."),
    ("ID_Comentario", "Identificador del comentario. Instagram: nativo. Facebook (fb_…) y TikTok (tt_…): sintético, hash del texto y autor."),
    ("ID_Comentario_Padre", "Comentario al que responde, si es una respuesta."),
    ("Autor", "Nombre visible del autor."),
    ("Usuario_Arroba", "Nombre de usuario (@)."),
    ("Texto_Comentario", "Texto del comentario."),
    ("Fecha_Comentario", "Fecha del comentario. Con '~' delante es aproximada (calculada desde 'hace 2 d')."),
    ("Fecha_Precision", "Precisión de la fecha del comentario."),
    ("Likes_Comentario", "Me gusta del comentario."),
    ("Respuestas_Comentario", "Respuestas que la plataforma declara para ese comentario."),
    ("Nivel_Comentario", "0 = comentario a la publicación, 1 = respuesta (incluye las inferidas de Facebook)."),
    ("Segundos_Desde_Post", "Segundos entre la publicación y el comentario (si ambas fechas son exactas)."),
    ("Post_Fecha", "Fecha de la publicación."),
    ("Post_Likes", "Me gusta de la publicación (0 = no disponible u oculto por el autor)."),
    ("Post_Comentarios_Total", "Comentarios que declara la plataforma (no siempre alcanzable)."),
    ("Post_Shares", "Compartidos (si la plataforma lo muestra)."),
    ("Post_Views", "Reproducciones (no visibles en ninguna de las tres desde la web: 0)."),
    ("Ventana_Debate", "Tiempo entre el primer y el último comentario de esa extracción."),
    ("URL_Origen", "Enlace de la publicación."),
    ("ID_Caso", "Caso asignado en la extensión al extraer (vacío si no se asignó)."),
    ("Fecha_Extraccion", "Momento de la extracción."),
    ("ID_Extraccion", "Identificador de la corrida de extracción."),
    ("Duplicado_Exacto", "Fila idéntica a otra en TODAS sus columnas (extracción repetida). Es False en todo el corpus. NO marca textos repetidos: para eso hay que normalizar Texto_Comentario."),
    ("Duplicado_Por_ID", "Mismo ID_Comentario que otra fila de la misma plataforma. En Facebook y TikTok el ID es un hash de autor+texto, así que marca a la misma persona pegando el mismo comentario en otra publicación (nunca dentro de la misma). La clave única es ID_Post_Origen + ID_Comentario."),
    ("Parent_Source", "Origen del vínculo con el padre: ID explícito o mención inicial inferida."),
    ("Parent_Confidence", "Confianza de ese vínculo."),
    ("Texto_Truncado", "El texto parece cortado por la plataforma."),
    ("Archivo_Origen", "CSV crudo de origen (en la carpeta crudos/ de su plataforma)."),
    ("Fila_Origen", "Fila dentro de ese CSV."),
]
NUMERICAS = {"Likes_Comentario", "Respuestas_Comentario", "Nivel_Comentario", "Segundos_Desde_Post",
             "Post_Likes", "Post_Comentarios_Total", "Post_Shares", "Post_Views", "Fila_Origen",
             "Filas", "Comentarios", "Respuestas", "Publicaciones", "Con texto", "Fecha exacta",
             "Fecha aproximada", "Sin fecha", "Autores únicos"}
HEADER_FILL = PatternFill("solid", fgColor="1F2A30")
HEADER_FONT = Font(bold=True, color="FFFFFF")


def leer_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def armonizar(crudos):
    """Pasa una carpeta de crudos por build_corpus.py y devuelve (comentarios, posts, registro)."""
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [sys.executable, str(AQUI / "build_corpus.py"), "--raw-dir", str(crudos), "--output-dir", tmp]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            raise SystemExit(f"build_corpus.py falló sobre {crudos}:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
        t = Path(tmp)
        return leer_csv(t / "comments.csv"), leer_csv(t / "posts.csv"), leer_csv(t / "publication_registry.csv")


def es_respuesta(r):
    return r.get("Tipo_Elemento") == "Respuesta" or r.get("Nivel_Comentario") == "1"


def valor(col, v):
    if v is None or v == "":
        return None
    if col in NUMERICAS:
        try:
            f = float(v)
            return int(f) if f.is_integer() else f
        except ValueError:
            pass
    return ILLEGAL_CHARACTERS_RE.sub("", str(v))


def hoja(ws, columnas, filas, anchos=None):
    ws.append(columnas)
    for c in ws[1]:
        c.fill, c.font = HEADER_FILL, HEADER_FONT
    for fila in filas:
        ws.append([valor(col, fila.get(col)) for col in columnas])
    # Un texto que empieza con "=", "+", "-" o "@" se guardaría como fórmula: forzarlo a texto.
    for row in ws.iter_rows(min_row=2):
        for c in row:
            if isinstance(c.value, str) and c.value[:1] in "=+-@" and len(c.value) > 1:
                c.data_type = "s"
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for i, col in enumerate(columnas, 1):
        ws.column_dimensions[get_column_letter(i)].width = (anchos or {}).get(col, max(12, min(30, len(col) + 2)))


def publicaciones(comentarios, posts, registro):
    por_post = defaultdict(Counter)
    archivo, autor = {}, {}
    for r in comentarios:
        por_post[r["ID_Post_Origen"]]["Respuesta" if es_respuesta(r) else "Comentario"] += 1
        archivo.setdefault(r["ID_Post_Origen"], r.get("Archivo_Origen", ""))
    posts_por_id = {p["ID_Post_Origen"]: p for p in posts}
    filas = []
    for reg in registro:
        pid = reg["ID_Post_Origen"]
        p = posts_por_id.get(pid, {})
        c = por_post[pid]
        filas.append({
            "Plataforma": reg["Plataforma"], "Archivo_Origen": archivo.get(pid, ""), "ID_Post_Origen": pid,
            "Post_Fecha": p.get("Post_Fecha", ""), "Post_Likes": p.get("Post_Likes", ""),
            "Post_Shares": p.get("Post_Shares", ""), "Post_Comentarios_Total": p.get("Post_Comentarios_Total", ""),
            "Comentarios": c["Comentario"], "Respuestas": c["Respuesta"], "Filas": c["Comentario"] + c["Respuesta"],
            "URL_Origen": reg.get("URL_Origen") or p.get("URL_Origen", ""),
        })
    filas.sort(key=lambda x: (x["Plataforma"], -x["Filas"]))
    return filas


PUB_COLS = ["Plataforma", "Archivo_Origen", "ID_Post_Origen", "Post_Fecha", "Post_Likes", "Post_Shares",
            "Post_Comentarios_Total", "Comentarios", "Respuestas", "Filas", "URL_Origen"]


def resumen(comentarios, pubs):
    filas = []
    plats = sorted({r["Plataforma"] for r in comentarios})
    for plat in plats + (["Total"] if len(plats) > 1 else []):
        rs = comentarios if plat == "Total" else [r for r in comentarios if r["Plataforma"] == plat]
        fechas = [r.get("Fecha_Comentario") or "" for r in rs]
        filas.append({
            "Plataforma": plat,
            "Publicaciones": sum(1 for p in pubs if plat in ("Total", p["Plataforma"])),
            "Filas": len(rs),
            "Comentarios": sum(not es_respuesta(r) for r in rs),
            "Respuestas": sum(es_respuesta(r) for r in rs),
            "Con texto": sum(bool((r.get("Texto_Comentario") or "").strip()) for r in rs),
            "Fecha exacta": sum(bool(f) and not f.startswith("~") for f in fechas),
            "Fecha aproximada": sum(f.startswith("~") for f in fechas),
            "Sin fecha": sum(not f for f in fechas),
            "Autores únicos": len({r.get("Usuario_Arroba") or r.get("Autor") for r in rs}),
        })
    return filas


NOTAS = {
    "Facebook": "Fechas de comentarios aproximadas con precisión de UNA SEMANA ('~'; calculadas desde 'hace N sem'): no sirven para análisis por día. Respuestas inferidas por mención inicial (Tipo_Elemento = Comentario, Nivel_Comentario = 1). Post_Likes no se captura (0).",
    "Instagram": "Re-extraído el 2026-10-20 con la extensión v1.19–v1.23 y 'Abrir comentarios ocultos' activado. Fechas exactas. Los comentarios que son solo un GIF no se capturan (~1 %).",
    "TikTok": "Extraído el 2026-10-21 con la extensión v1.24–v1.25. Fechas de comentarios por día (sin hora). El contador de TikTok no es alcanzable: su API deja de entregar antes.",
}


def escribir_excel(destino, comentarios, posts, registro):
    pubs = publicaciones(comentarios, posts, registro)
    wb = Workbook()
    ws = wb.active
    ws.title = "Comentarios"
    comentarios = sorted(comentarios, key=lambda r: (r["Plataforma"], r["ID_Post_Origen"], r.get("Fecha_Comentario") or ""))
    hoja(ws, [c for c, _ in COLUMNAS], comentarios,
         {"Texto_Comentario": 80, "Autor": 22, "Usuario_Arroba": 22, "URL_Origen": 45})
    hoja(wb.create_sheet("Publicaciones"), PUB_COLS, pubs, {"URL_Origen": 75, "ID_Post_Origen": 26})
    res = wb.create_sheet("Resumen")
    hoja(res, ["Plataforma", "Publicaciones", "Filas", "Comentarios", "Respuestas", "Con texto",
               "Fecha exacta", "Fecha aproximada", "Sin fecha", "Autores únicos"], resumen(comentarios, pubs))
    res.append([])
    res.append([f"Generado el {FECHA} con generar_bases.py (armonizado con build_corpus.py). Ver README.md."])
    for plat in sorted({r["Plataforma"] for r in comentarios}):
        res.append([plat, NOTAS.get(plat, "")])
    dic = wb.create_sheet("Diccionario")
    dic.append(["Columna", "Descripción"])
    for c in dic[1]:
        c.fill, c.font = HEADER_FILL, HEADER_FONT
    for col, desc in COLUMNAS:
        dic.append([col, desc])
    dic.column_dimensions["A"].width = 26
    dic.column_dimensions["B"].width = 110
    wb.save(destino)
    return pubs


def escribir_inventario(destino, pubs):
    with open(destino, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=PUB_COLS)
        w.writeheader()
        w.writerows(pubs)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datos", type=Path, default=AQUI.parent / "datos" / "bases_armonizadas",
                    help="Carpeta con Facebook_Instagram/crudos/ y TikTok/crudos/. Ahí se escriben las bases.")
    datos = ap.parse_args().datos.resolve()
    for sub in ("Facebook_Instagram", "TikTok"):
        if not (datos / sub / "crudos").is_dir():
            raise SystemExit(f"No encuentro {datos / sub / 'crudos'}. Ver datos/README.md.")

    fbig = armonizar(datos / "Facebook_Instagram" / "crudos")
    tt = armonizar(datos / "TikTok" / "crudos")

    p1 = escribir_excel(datos / "Facebook_Instagram" / f"base_armonizada_FB_IG_{FECHA}.xlsx", *fbig)
    escribir_inventario(datos / "Facebook_Instagram" / "inventario_publicaciones.csv", p1)
    p2 = escribir_excel(datos / "TikTok" / f"base_armonizada_TikTok_{FECHA}.xlsx", *tt)
    escribir_inventario(datos / "TikTok" / "inventario_publicaciones.csv", p2)
    juntos = [a + b for a, b in zip(fbig, tt)]
    p3 = escribir_excel(datos / f"base_armonizada_FB_IG_TikTok_{FECHA}.xlsx", *juntos)

    for nombre, (com, _, _), pubs in [("FB+IG", fbig, p1), ("TikTok", tt, p2), ("FB+IG+TikTok", juntos, p3)]:
        cuenta = Counter(r["Plataforma"] for r in com)
        print(f"{nombre:14s} publicaciones {len(pubs):3d} | filas {len(com):6d} | {dict(cuenta)}")


if __name__ == "__main__":
    main()
