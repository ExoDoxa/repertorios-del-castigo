import csv, json, re, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill

sys.stdout.reconfigure(encoding="utf-8")
import argparse
_ap = argparse.ArgumentParser(description="Construye el registro de publicaciones (texto, cuenta, tipo, formato, transcripción).")
_ap.add_argument("--datos", type=Path, default=Path(__file__).resolve().parent.parent / "datos" / "bases_armonizadas",
                 help="Carpeta de las bases (con los inventario_publicaciones.csv); ahí se escribe el registro.")
_ap.add_argument("--capturas", type=Path, default=None,
                 help="Carpeta con captions_fb.json, captions_ig.json, captions_tt.json y transcripciones_manuales_*.json "
                      "(por defecto <datos>/registro_publicaciones_crudo).")
_args = _ap.parse_args()
OUT = _args.datos.resolve()
PW = (_args.capturas or OUT / "registro_publicaciones_crudo").resolve()
VERIF = "2026-10-22"
COL = timezone(timedelta(hours=-5))

def load(p):
    return json.load(open(PW / p, encoding="utf-8"))

fb = {r["archivo"]: r for r in load("captions_fb.json")}
ig = {r["archivo"]: r for r in load("captions_ig.json") if r["plataforma"] == "Instagram"}
ttall = load("captions_tt.json")
tt = {r["archivo"]: r for r in ttall if r.get("plataforma") == "TikTok"}
reel_auth = {r["archivo"]: r["reel_links"][0][0] for r in ttall if r.get("plataforma") == "Facebook" and r.get("reel_links")}

inv = []
for f in ["Facebook_Instagram/inventario_publicaciones.csv", "TikTok/inventario_publicaciones.csv"]:
    inv += list(csv.DictReader(open(OUT / f, encoding="utf-8-sig")))

# Tipo de cuenta PROPUESTO (a verificar con la biografía / página de información)
TIPO = {
    "Face1.csv": ("creador de contenido", "Perfil de creador (persona física); el mismo texto y video aparecen en su TikTok (tt16)"),
    "face13.csv": ("creador de contenido", "La candelita: categoría 'Digital creator'; bio 'videos de humor y entretenimiento, reflexiones' (verificado 2026-10-22). Publica noticias sin citar fuente"),
    "Face12.csv": ("página de noticias sin redacción", "Alerta informativa: categoría 'Media/news company', sin redacción, web ni contacto editorial en la información de la página (verificado 2026-10-22); la crónica la firma 'Keider Jose'"),
    "Face3.csv": ("", "Publicación eliminada"),
    "Face4.csv": ("medio local o regional", "Santa Marta Stereo (emisora)"),
    "Face7.csv": ("página de noticias sin redacción", "PCT EN LA NOTICIA; enlaza nota de canalcampotv.com"),
    "Face9.csv": ("página de noticias sin redacción", "El Cold (página de contenido viral)"),
    "FACE2.csv": ("particular", "Perfil personal"),
    "face15.csv": ("página de noticias sin redacción", "Reportando Noticias"),
    "Face14.csv": ("otro", "Diccionario Costeño: página de humor/cultura regional que publica noticias"),
    "Face8.csv": ("página de noticias sin redacción", "Información Veraz Objetiva y Oportuna"),
    "Face11.csv": ("página de noticias sin redacción", "Ciénaga al Rojo vivo (página judicial local)"),
    "Face6.csv": ("otro", "Periodista y locutor local que publica desde su perfil personal, no desde un medio"),
    "Face10.csv": ("página de noticias sin redacción", "Última Hora - La Loma"),
    "Face5.csv": ("página de noticias sin redacción", "El Retén y La Noticia"),
    "inst1.csv": ("medio local o regional", "Última Hora Magdalena: bio con sitio web (ultimahoramagdalena.com.co), teléfono y sede en Santa Marta (verificado 2026-10-22). Caso de frontera: no nombra redacción"),
    "inst14.csv": ("medio local o regional", "Santa Marta Al Día"),
    "inst5.csv": ("medio local o regional", "Guajira News"),
    "INST7.csv": ("medio local o regional", "Semanario La Calle (Valledupar)"),
    "Inst6.csv": ("medio nacional", "Cablenoticias: bio 'Canal de televisión', cablenoticias.com (verificado 2026-10-22). Misma entidad que tt18 (TikTok)"),
    "inst8.csv": ("medio local o regional", "Guajira News"),
    "inst11.csv": ("página de noticias sin redacción", "La certeza"),
    "inst4.csv": ("medio nacional", "La Kalle (emisora nacional)"),
    "inst9.csv": ("creador de contenido", "Informe fantasma (relatos de crímenes)"),
    "inst12.csv": ("medio local o regional", "guajira24horas.com"),
    "Inst3.csv": ("medio local o regional", "Guajira News"),
    "inst13.csv": ("medio local o regional", "Diario del Norte (La Guajira)"),
    "inst10.csv": ("medio local o regional", "Hoy Diario del Magdalena: bio 'Medio de comunicación/noticias. Periódico' (verificado 2026-10-22)"),
    "Inst2.csv": ("medio local o regional", "TuBarco | Medio Digital"),
    "Tiktok7.csv": ("creador de contenido", "Bio: 'Chismes y recomendaciones'"),
    "tt15.csv": ("vidente o esotérico", "Bio de vidente y guía espiritual"),
    "tt19.csv": ("página de noticias sin redacción", "Bio: 'últimas novedades'; formato greenscreen"),
    "Tiktok3.csv": ("página de noticias sin redacción", "Bio: 'últimas novedades'; formato greenscreen"),
    "tt17.csv": ("vidente o esotérico", "Bio: 'Clarividente De Nacimiento, Mago, Tarot'"),
    "tt16.csv": ("creador de contenido", "Creador (persona física); mismo texto y video que su reel de Facebook (Face1)"),
    "tt12.csv": ("medio local o regional", "La Provincia (bio: 'Valledupar, Cesar')"),
    "tt20.csv": ("creador de contenido", "Bio: 'Creador de contenido'"),
    "tt10.csv": ("creador de contenido", "Bio: 'Chismes y recomendaciones'"),
    "Tiktok2.csv": ("particular", "Usuario sin nombre ni biografía"),
    "Tiktok4.csv": ("página de noticias sin redacción", "HTV Noticias; bio 'Noticias nacionales eh internacionales'"),
    "tt14.csv": ("página de noticias sin redacción", "DN Noticias Atlántico"),
    "Tiktok6.csv": ("medio nacional", "Red+ Noticias (canal de TV); verificar"),
    "tt13.csv": ("creador de contenido", "Bio: 'Chismes y recomendaciones'"),
    "tt18.csv": ("medio nacional", "Cablenoticias (bio: canal 100% noticias, cableoperadores). Misma entidad que Inst6 (Instagram)"),
    "Tiktokk5.csv": ("particular", "Perfil personal sin biografía"),
}

# Imágenes del propio post (>=250 px) en las publicaciones de Facebook que no son reels; ninguna tenía <video>
FB_IMG = {"face13.csv": 2, "Face12.csv": 2, "Face4.csv": 1, "Face7.csv": 1, "Face9.csv": 2, "face15.csv": 1,
          "Face14.csv": 3, "Face8.csv": 3, "Face11.csv": 2, "Face6.csv": 3, "Face10.csv": 3, "Face5.csv": 3}

def vtt_to_text(raw):
    lines = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("WEBVTT") or "-->" in ln or re.fullmatch(r"\d+", ln):
            continue
        if not lines or lines[-1] != ln:
            lines.append(ln)
    return " ".join(lines)

def to_dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

MANUAL = json.load(open(PW / "transcripciones_manuales_2026-10-22.json", encoding="utf-8"))

rows = []
for r in inv:
    f, plat, url = r["Archivo_Origen"], r["Plataforma"], r["URL_Origen"]
    pf = to_dt(r["Post_Fecha"]) if r["Post_Fecha"] else None
    row = {
        "Plataforma": plat, "Archivo_Origen": f, "ID_Post_Origen": r["ID_Post_Origen"], "URL_Origen": url,
        "Estado": "disponible", "Fecha_Verificacion": VERIF,
        "Cuenta_Nombre": "", "Cuenta_Usuario": "", "Tipo_Cuenta_Propuesto": TIPO.get(f, ("", ""))[0],
        "Evidencia_Tipo_Cuenta": TIPO.get(f, ("", ""))[1], "Biografia_Cuenta": "",
        "Formato": "", "Post_Fecha_UTC": r["Post_Fecha"],
        "Post_Fecha_Colombia": pf.astimezone(COL).strftime("%Y-%m-%d %H:%M") if pf else "",
        "Control_Fecha": "", "Texto_Publicacion": "",
        "Contenido_Audiovisual": "", "Fuente_Contenido_Audiovisual": "",
        "Likes_Leidos": "", "Comentarios_Leidos": "", "Vistas_Leidas": "", "Compartidos_Leidos": "",
        "Notas": "",
    }
    if f == "Face3.csv":
        row.update(Estado="eliminada", Notas="Reel eliminado; los comentarios se capturaron cuando estaba disponible.")
    elif plat == "Facebook":
        d = fb[f]
        row["Texto_Publicacion"] = d.get("texto", "")
        if "/reel/" in url:
            row["Formato"] = "reel (video)"
            row["Cuenta_Nombre"] = reel_auth.get(f, "")
        else:
            n_img = FB_IMG.get(f)
            row["Formato"] = f"texto + {n_img} {'imagen' if n_img == 1 else 'imágenes'} (sin video; verificado 2026-10-22)" if n_img else "publicación (por verificar)"
            row["Cuenta_Nombre"] = re.sub(r"'s Post$", "", d.get("autor_h2", ""))
        m = re.search(r"facebook\.com/([^/?]+)/posts/", url)
        row["Cuenta_Usuario"] = m.group(1) if m else ""
        row["Control_Fecha"] = "fecha ya verificada en la extracción (Post_Fecha desde el JSON de la página)"
        if f == "Face4.csv":
            row["Notas"] = "La URL es de 'misterbalin' pero la publicación se muestra como de Santa Marta Stereo. Es un desmentido: la madre de otra niña pide bajar un video mal atribuido."
        if f == "Face1.csv":
            row["Notas"] = "Texto truncado por Facebook en el reel; el texto completo es el mismo que el de tt16 (TikTok, misma cuenta)."
            row["Texto_Publicacion"] = tt["tt16.csv"]["desc"] if row["Texto_Publicacion"].endswith("See more") else row["Texto_Publicacion"]
            row["Contenido_Audiovisual"] = vtt_to_text(tt["tt16.csv"]["transcripcion_raw"])
            row["Fuente_Contenido_Audiovisual"] = "transcripción de tt16: mismo video (152,6 s en Facebook, 152 s en TikTok, misma cuenta), subtítulos automáticos de TikTok"
        if not row["Fuente_Contenido_Audiovisual"]:
            row["Fuente_Contenido_Audiovisual"] = "pendiente: Facebook no expone subtítulos; ver el video" if ("reel" in row["Formato"]) else "no aplica (sin video; las imágenes no se describen)"
    elif plat == "Instagram":
        d = ig[f]
        t = d.get("og_title", "")
        m = re.match(r'^(.*?) en Instagram: "(.*)"$', t, re.S)
        row["Cuenta_Nombre"] = m.group(1) if m else ""
        row["Texto_Publicacion"] = m.group(2) if m else t
        dm = re.match(r"^(?:([\d,.KkM]+) likes?, )?(?:([\d,.KkM]+) comments? - )?(\S+) el (\w+ \d+, \d{4})", d.get("og_desc", ""))
        if dm:
            row["Likes_Leidos"], row["Comentarios_Leidos"], row["Cuenta_Usuario"] = dm.group(1) or "oculto", dm.group(2) or "", dm.group(3)
            dd = datetime.strptime(dm.group(4), "%B %d, %Y").date()
            loc = pf.astimezone(COL).date() if pf else None
            utc = pf.date() if pf else None
            pac = (pf - timedelta(hours=8)).date() if pf else None
            row["Control_Fecha"] = f"página: {dd} (Instagram la muestra en hora del Pacífico, UTC-8) | " + ("coincide" if dd in (loc, utc, pac) else "NO coincide")
        row["Formato"] = "reel (video)" if "/reels/" in url else ("video" if d.get("video") else "foto o carrusel")
        row["Fuente_Contenido_Audiovisual"] = "pendiente: Instagram no expone subtítulos; ver el video" if "video" in row["Formato"] else "no aplica (imagen)"
    else:
        d = tt[f]
        row["Cuenta_Nombre"], row["Cuenta_Usuario"] = d.get("autor", ""), d.get("usuario", "")
        row["Biografia_Cuenta"] = (d.get("bio") or "").replace("\n", " | ")
        row["Texto_Publicacion"] = d.get("desc", "")
        row["Formato"] = "video (greenscreen)" if "#greenscreen" in (d.get("desc") or "").lower() else "video"
        row["Formato"] += f", {d.get('duracion')} s"
        ct = datetime.fromtimestamp(int(d["createTime"]), timezone.utc)
        row["Control_Fecha"] = f"página: {ct.strftime('%Y-%m-%dT%H:%M:%SZ')} | " + (f"coincide (Post_Fecha, decodificada del ID, va {int((ct - pf).total_seconds())} s antes: el ID marca el inicio de la subida)" if pf and 0 <= (ct - pf).total_seconds() < 120 else "NO coincide")
        if not d.get("url_final", "").endswith(r["ID_Post_Origen"]):
            row["Control_Fecha"] += " | OJO: la página abrió otra URL"
        st = d.get("stats") or {}
        row["Likes_Leidos"], row["Comentarios_Leidos"], row["Vistas_Leidas"], row["Compartidos_Leidos"] = (
            st.get("diggCount", ""), st.get("commentCount", ""), st.get("playCount", ""), st.get("shareCount", ""))
        if d.get("transcripcion_raw"):
            row["Contenido_Audiovisual"] = vtt_to_text(d["transcripcion_raw"])
            row["Fuente_Contenido_Audiovisual"] = f"subtítulos automáticos de TikTok ({d.get('transcripcion_lang')}); reconocimiento de voz sin corregir"
        else:
            row["Fuente_Contenido_Audiovisual"] = "pendiente: el video no tiene subtítulos automáticos"
    if f in MANUAL and MANUAL[f].get("visual"):
        row["Notas"] = (row["Notas"] + " | " if row["Notas"] else "") + MANUAL[f]["visual"]
    if f in MANUAL and MANUAL[f].get("texto") and not row["Contenido_Audiovisual"]:
        row["Contenido_Audiovisual"] = MANUAL[f]["texto"]
        row["Fuente_Contenido_Audiovisual"] = MANUAL[f]["fuente"]
    rows.append(row)

cols = list(rows[0])
with open(OUT / "registro_publicaciones_2026-10-22.csv", "w", encoding="utf-8-sig", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows)

wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Publicaciones"
ws.append(cols)
for r in rows:
    ws.append([("'" + v if isinstance(v, str) and v[:1] in "=+-@" else v) for v in (r[c] for c in cols)])
for c in ws[1]:
    c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="305496")
widths = {"Texto_Publicacion": 80, "Contenido_Audiovisual": 80, "Evidencia_Tipo_Cuenta": 40, "Biografia_Cuenta": 35, "URL_Origen": 35, "Notas": 40}
for i, c in enumerate(cols, 1):
    ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = widths.get(c, 18)
for row in ws.iter_rows(min_row=2):
    for c in row:
        c.alignment = Alignment(wrap_text=True, vertical="top")
ws.freeze_panes = "C2"; ws.auto_filter.ref = ws.dimensions
n = wb.create_sheet("Notas")
for line in [
    "Registro de publicaciones del corpus (45 claves; 44 disponibles + Face3 eliminada). Leído el 2026-10-22 con un navegador con sesión iniciada.",
    "Texto_Publicacion: Facebook = cuerpo de la publicación tras expandir 'Ver más'; Instagram = caption (meta og:title); TikTok = descripción del video (JSON de la página).",
    "Tipo_Cuenta_Propuesto: propuesta automática a partir del nombre y la biografía. Verificar con la página de información de cada cuenta. Criterio de desempate: ¿hay una redacción identificable?",
    "Contenido_Audiovisual: solo TikTok trae transcripción (subtítulos automáticos de la plataforma, con errores de reconocimiento de voz). Facebook e Instagram quedan pendientes de ver el video.",
    "Post_Fecha_Colombia = Post_Fecha_UTC - 5 h. Control_Fecha: contrastado contra la página en 30 publicaciones (14 de Instagram, solo al día; 16 de TikTok, al segundo). Las 14 de Facebook no tienen control independiente: Post_Fecha ya salía del JSON de la propia página.",
    "Likes/Comentarios/Vistas/Compartidos_Leidos: lo que mostraba la plataforma el 2026-10-22 (Instagram y TikTok). Las de Facebook están en Facebook_Instagram/metricas_facebook_2026-10-22.csv.",
    "Cuentas de particulares (FACE2, Face6, Tiktok2, Tiktokk5): anonimizar en el artículo.",
]:
    n.append([line])
n.column_dimensions["A"].width = 160
wb.save(OUT / "registro_publicaciones_2026-10-22.xlsx")

from collections import Counter
print(len(rows), Counter(r["Estado"] for r in rows))
print("sin texto:", [r["Archivo_Origen"] for r in rows if r["Estado"] == "disponible" and not r["Texto_Publicacion"]])
print("sin cuenta:", [r["Archivo_Origen"] for r in rows if r["Estado"] == "disponible" and not r["Cuenta_Nombre"]])
print("control NO:", [(r["Archivo_Origen"], r["Control_Fecha"]) for r in rows if "NO" in r["Control_Fecha"] or "OJO" in r["Control_Fecha"]])
print("transcripciones:", sum(1 for r in rows if r["Contenido_Audiovisual"]))
print(Counter(r["Tipo_Cuenta_Propuesto"] for r in rows))
