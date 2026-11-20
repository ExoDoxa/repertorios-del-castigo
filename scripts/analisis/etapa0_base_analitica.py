# -*- coding: utf-8 -*-
"""Etapa 0 — Base analítica del corpus de Mingueo.
Lee la base armonizada y el registro de publicaciones y genera:
  corpus_analitico.parquet, publicaciones_analitico.csv, verificacion_etapa0.csv
Todas las columnas derivadas se documentan en diccionario_variables.md.
Uso: python etapa0_base_analitica.py   (la carpeta de las bases se toma de la variable EXODOXA_DATOS o de datos/bases_armonizadas)
"""
import os, re, unicodedata
import pandas as pd, numpy as np

DATA_DIR = os.environ.get("EXODOXA_DATOS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "datos", "bases_armonizadas"))
OUT_DIR = "."
BASE = os.path.join(DATA_DIR, "base_armonizada_FB_IG_TikTok_2026-10-21.xlsx")
REG = os.path.join(DATA_DIR, "registro_publicaciones_2026-10-22.xlsx")
TZ_COT = "America/Bogota"  # UTC-5 sin horario de verano

com = pd.read_excel(BASE, sheet_name="Comentarios", dtype=str, keep_default_na=False, na_values=[""])
reg = pd.read_excel(REG, sheet_name="Publicaciones", dtype=str, keep_default_na=False, na_values=[""])
for c in ["Likes_Comentario", "Respuestas_Comentario", "Nivel_Comentario", "Post_Comentarios_Total", "Post_Likes"]:
    com[c] = pd.to_numeric(com[c], errors="coerce")

# --- clave y tipo de fila ---------------------------------------------------
com["clave_comentario"] = com["ID_Post_Origen"] + "|" + com["ID_Comentario"]
com["es_respuesta"] = com["Nivel_Comentario"].eq(1)

# --- tiempo ----------------------------------------------------------------
ig = com["Plataforma"].eq("Instagram"); tt = com["Plataforma"].eq("TikTok"); fb = com["Plataforma"].eq("Facebook")
fu = pd.to_datetime(com["Fecha_Comentario"].where(ig), utc=True, errors="coerce")
com["fecha_utc_ig"] = fu
com["fecha_cot_ig"] = fu.dt.tz_convert(TZ_COT)
com["dia_cot"] = pd.NaT
com.loc[ig, "dia_cot"] = com.loc[ig, "fecha_cot_ig"].dt.tz_localize(None).dt.normalize()
com.loc[tt, "dia_cot"] = pd.to_datetime(com.loc[tt, "Fecha_Comentario"], errors="coerce")   # a día; zona de TikTok desconocida
com["dia_cot"] = pd.to_datetime(com["dia_cot"])
com["hora_cot_ig"] = com["fecha_cot_ig"].dt.hour
com["semana_aprox_fb"] = pd.to_datetime(com["Fecha_Comentario"].where(fb).str.lstrip("~"), errors="coerce")
pf = pd.to_datetime(com["Post_Fecha"], utc=True, errors="coerce")
com["post_fecha_cot"] = pf.dt.tz_convert(TZ_COT)
com["post_dia_cot"] = com["post_fecha_cot"].dt.tz_localize(None).dt.normalize()

# ventanas de Instagram (hora de Colombia, 11-dic-2025); cotas: ver cronologia_caso_mingueo.md
t = lambda s: pd.Timestamp(s, tz=TZ_COT)
cotas = [t("2025-12-11 09:46"), t("2025-12-11 12:06"), t("2025-12-11 13:33"), t("2025-12-12 00:00")]
etq = ["W0 antes de la primera publicación del corpus que informa la detención (<09:46)",
       "W1 09:46–12:06 (detención informada; aún ningún comentario alude a la muerte)",
       "W2 12:06–13:33 (primer comentario que alude a la muerte; aún no la afirma)",
       "W3 13:33–24:00 del 11-dic (muerte afirmada en comentarios)",
       "W4 desde el 12-dic"]
v = pd.Series(pd.NA, index=com.index, dtype="object")
f = com["fecha_cot_ig"]
v[ig & (f < cotas[0])] = etq[0]; v[ig & (f >= cotas[0]) & (f < cotas[1])] = etq[1]
v[ig & (f >= cotas[1]) & (f < cotas[2])] = etq[2]; v[ig & (f >= cotas[2]) & (f < cotas[3])] = etq[3]; v[ig & (f >= cotas[3])] = etq[4]
com["ventana_ig"] = v

# --- publicaciones: tipo, política de nombre, formato, marcas ----------------------------------
reg["tipo_cuenta"] = reg["Tipo_Cuenta_Propuesto"].fillna("").str.strip("'").str.strip()
reg.loc[reg["Estado"].eq("eliminada"), "tipo_cuenta"] = "no determinado (publicación eliminada)"
reg["post_eliminada"] = reg["Estado"].eq("eliminada")
# Reclasificación decidida por el autor el 22-oct-2026 (D-14): inst9 es una página-marca (20 mil seguidores, sin nombre de persona).
reg.loc[reg["Archivo_Origen"].str.lower().eq("inst9.csv"), "tipo_cuenta"] = "página de noticias sin redacción"
# Política de nombre PROPUESTA (confirmar): se nombran medios y páginas; se anonimiza a toda persona física.
# Excepciones explícitas: face13 (página nombrada por decisión del autor); Face14 (página de humor) se nombra;
# Face6 (periodista desde perfil personal) se anonimiza; inst9 es página (se nombra).
persona = {"particular", "vidente o esotérico"}
nombrar = {"medio nacional", "medio local o regional", "página de noticias sin redacción"}
def politica(r):
    a = r["Archivo_Origen"].lower()
    if r["post_eliminada"]: return "no nombrar (publicación eliminada)"   # D-09: se describe como «una publicación de Facebook eliminada después de la extracción»
    if a == "face13.csv": return "nombrar"
    if a == "face14.csv": return "nombrar"
    if a == "face6.csv": return "anonimizar"
    if r["tipo_cuenta"] in nombrar: return "nombrar"
    if r["tipo_cuenta"] in persona or r["tipo_cuenta"] == "creador de contenido": return "anonimizar"
    return "por confirmar"
reg["politica_nombre"] = reg.apply(politica, axis=1)
cod = {}; n = 0
def etiqueta(r):
    global n
    if r["post_eliminada"]: return "publicación de Facebook eliminada después de la extracción"
    if r["politica_nombre"] == "nombrar": return r["Cuenta_Nombre"]
    key = (r["Cuenta_Nombre"] or "").strip().lower().replace(" ", "")
    if key not in cod: n += 1; cod[key] = f"cuenta anonimizada {n:02d}"
    return cod[key]
reg["cuenta_etiqueta"] = reg.apply(etiqueta, axis=1)
# Cuentas que publican dos veces en la misma plataforma o en dos plataformas comparten etiqueta solo si el nombre es idéntico;
# el caso FB+TikTok de un creador (nombres distintos) se une a mano abajo.
solo_caption = {"inst6.csv", "inst8.csv", "inst11.csv", "inst4.csv", "inst9.csv", "inst12.csv", "inst3.csv", "inst10.csv"}
reg["postura_solo_caption"] = reg["Archivo_Origen"].str.lower().isin(solo_caption)
reg["formato_post"] = reg["Formato"].str.replace(r"\s*\(sin video; verificado.*?\)", "", regex=True)

pub = reg[["Plataforma", "Archivo_Origen", "ID_Post_Origen", "tipo_cuenta", "politica_nombre", "cuenta_etiqueta",
           "formato_post", "postura_solo_caption", "post_eliminada", "Post_Fecha_Colombia", "Control_Fecha"]].copy()
com = com.merge(pub[["Archivo_Origen", "tipo_cuenta", "politica_nombre", "cuenta_etiqueta", "formato_post",
                     "postura_solo_caption", "post_eliminada"]], on="Archivo_Origen", how="left", validate="m:1")

# --- texto ----------------------------------------------------------------
def norm(s):
    if not isinstance(s, str): return ""
    s = unicodedata.normalize("NFKD", s.lower()); s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", s).strip()
com["texto_norm"] = com["Texto_Comentario"].map(norm)
com["texto_vacio"] = com["texto_norm"].eq("")
com["solo_emoji"] = ~com["texto_vacio"] & ~com["texto_norm"].str.contains(r"[a-z0-9]", regex=True)
com["n_palabras"] = com["texto_norm"].str.findall(r"[a-z0-9]+").str.len()
g = com.groupby("clave_comentario").size()
npost_id = com.groupby("ID_Comentario")["ID_Post_Origen"].nunique()
com["id_repetido_entre_posts"] = com["ID_Comentario"].map(npost_id).gt(1)
cx = com[~com["texto_vacio"]].groupby("texto_norm")["ID_Post_Origen"].nunique()
com["n_posts_texto"] = com["texto_norm"].map(cx).fillna(0).astype(int)
com["texto_repetido_entre_posts"] = com["n_posts_texto"].ge(2)

# --- verificación contra las cifras ya verificadas ------------------------------------------
chk = []
def ok(nombre, esperado, obtenido): chk.append((nombre, esperado, obtenido, bool(esperado == obtenido)))
ok("filas", 15124, len(com))
for p, e in {"Facebook": 6205, "Instagram": 3023, "TikTok": 5896}.items(): ok(f"filas {p}", e, int(com.Plataforma.eq(p).sum()))
ok("comentarios (nivel 0)", 10274, int((~com.es_respuesta).sum())); ok("respuestas (nivel 1)", 4850, int(com.es_respuesta.sum()))
ok("publicaciones", 45, com.ID_Post_Origen.nunique() if False else com.Archivo_Origen.nunique())
ok("clave (post, comentario) única", 0, int(com.duplicated("clave_comentario").sum()))
ok("filas con id repetido entre publicaciones", 525, int(com.id_repetido_entre_posts.sum()))
ok("ids repetidos entre publicaciones", 153, int(com.loc[com.id_repetido_entre_posts, "ID_Comentario"].nunique()))
au = com.dropna(subset=["Usuario_Arroba"]).groupby("Plataforma")["Usuario_Arroba"].nunique()
ok("autores únicos por @ (total)", 12320, int(com["Usuario_Arroba"].nunique()))
for p, e in {"Facebook": 5180, "Instagram": 2445, "TikTok": 4695}.items(): ok(f"autores únicos {p}", e, int(au[p]))
igd = com.loc[ig, "dia_cot"].dt.strftime("%m-%d").value_counts()
for d, e in {"12-11": 897, "12-12": 1494, "12-13": 325, "12-14": 114, "12-15": 44, "12-16": 21}.items(): ok(f"Instagram {d} (hora de Colombia)", e, int(igd.get(d, 0)))
utc_day = com.loc[ig, "fecha_utc_ig"].dt.tz_localize(None).dt.normalize()
ok("Instagram: comentarios que cambian de día al convertir", 721, int((utc_day != com.loc[ig, "dia_cot"]).sum()))
ttd = com.loc[tt, "dia_cot"].dt.strftime("%m-%d").value_counts()
for d, e in {"12-11": 981, "12-12": 1583, "12-13": 1559, "12-14": 835, "12-15": 324, "12-16": 259, "12-17": 101}.items(): ok(f"TikTok {d} (día)", e, int(ttd.get(d, 0)))
ok("TikTok sin fecha", 87, int((tt & com.Fecha_Precision.eq("unknown")).sum())); ok("TikTok fecha aproximada", 9, int((tt & com.Fecha_Precision.eq("approximate")).sum()))
vw = com["ventana_ig"].value_counts()
for k, e in zip(etq, [351, 78, 29, 443, 2122]): ok(k[:2], e, int(vw.get(k, 0)))
tc = reg.drop_duplicates("Archivo_Origen")["tipo_cuenta"].value_counts()
for k, e in {"página de noticias sin redacción": 14, "medio local o regional": 12, "creador de contenido": 7, "medio nacional": 4, "particular": 3, "otro": 2, "vidente o esotérico": 2, "no determinado (publicación eliminada)": 1}.items(): ok(f"tipo de cuenta: {k}", e, int(tc.get(k, 0)))
ok("filas con postura_solo_caption", 524, int(com.postura_solo_caption.sum()))
ok("respuestas IG con vínculo explícito", 946, int((ig & com.Parent_Source.eq("explicit_id")).sum()))
ok("respuestas TikTok con vínculo explícito", 2997, int((tt & com.Parent_Source.eq("explicit_id")).sum()))
ok("respuestas FB con vínculo inferido", 901, int((fb & com.Parent_Source.eq("inferred_leading_author")).sum()))
ok("respuestas TikTok con vínculo inferido", 6, int((tt & com.Parent_Source.eq("inferred_leading_author")).sum()))
V = pd.DataFrame(chk, columns=["comprobación", "esperado", "obtenido", "coincide"])

# --- salida --------------------------------------------------------------
out_cols = [c for c in com.columns if c not in ("Autor",)]  # Autor (nombre visible) se conserva solo en la base original
com[out_cols].to_parquet(os.path.join(OUT_DIR, "corpus_analitico.parquet"), index=False)
pub.to_csv(os.path.join(OUT_DIR, "publicaciones_analitico.csv"), index=False, encoding="utf-8-sig")
V.to_csv(os.path.join(OUT_DIR, "verificacion_etapa0.csv"), index=False, encoding="utf-8-sig")
print(f"filas={len(com)}; columnas={len(out_cols)}; comprobaciones OK={int(V.coincide.sum())}/{len(V)}")
print(V[~V.coincide].to_string(index=False) if (~V.coincide).any() else "todas las cifras coinciden con las ya verificadas")
