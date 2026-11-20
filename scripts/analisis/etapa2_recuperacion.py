# -*- coding: utf-8 -*-
"""Etapa 2 — Recuperación léxica por repertorio.
Aplica lexico_v1.json (expresiones regulares sobre `texto_norm`) a corpus_analitico.parquet y escribe:
  indice_de_recuperacion.csv   una fila por comentario con una marca por repertorio
  conteos_de_recuperacion.csv  n absolutos «recuperados por el léxico» por repertorio y plataforma
  conteos_por_publicacion.csv  n absolutos por publicación y repertorio
El léxico es automático y no está validado: un comentario recuperado es un candidato para lectura, no un comentario codificado,
y los conteos NO son prevalencias. Uso: python etapa2_recuperacion.py [lexico.json]
"""
import json, re, sys
import pandas as pd

LEXICO = sys.argv[1] if len(sys.argv) > 1 else "lexico_v1.json"
com = pd.read_parquet("corpus_analitico.parquet")
lx = json.load(open(LEXICO, encoding="utf-8"))
comp = lambda pats: re.compile("|".join(f"(?:{p})" for p in pats))
txt = com["texto_norm"].fillna("")
con_texto = ~com["texto_vacio"]
I = com[["clave_comentario", "Plataforma", "Archivo_Origen", "es_respuesta", "cuenta_etiqueta"]].copy()
for r in lx["repertorios"]:
    if "subtipos" in r:
        subs = []
        for k, pats in r["subtipos"].items():
            rx = comp(pats); I[k] = txt.map(lambda s: bool(rx.search(s))) & con_texto; subs.append(k)
        I[r["id"]] = I[subs].any(axis=1)
    else:
        rx = comp(r["patrones"]); I[r["id"]] = txt.map(lambda s: bool(rx.search(s))) & con_texto
for k, pats in lx["terminos_aparte"].items():
    rx = comp(pats); I[k] = txt.map(lambda s: bool(rx.search(s))) & con_texto
RID = [r["id"] for r in lx["repertorios"]]
I["n_repertorios"] = I[RID].sum(axis=1); I["sin_recuperacion"] = con_texto & (I["n_repertorios"] == 0)
I.drop(columns=["cuenta_etiqueta"]).to_csv("indice_de_recuperacion.csv", index=False, encoding="utf-8-sig")

nombres = {r["id"]: r["nombre"] for r in lx["repertorios"]}
cols = RID + [c for r in lx["repertorios"] if "subtipos" in r for c in r["subtipos"]] + list(lx["terminos_aparte"])
rows = []
for plat in ["Facebook", "Instagram", "TikTok", "Total"]:
    d = I if plat == "Total" else I[I.Plataforma == plat]
    for c in cols:
        s = d[d[c]]
        rows.append({"repertorio": c, "nombre": nombres.get(c, c), "plataforma": plat, "rotulo": "recuperados por el léxico (no es prevalencia)",
                     "n_recuperados": len(s), "n_comentarios_nivel0": int((~s.es_respuesta).sum()), "n_respuestas": int(s.es_respuesta.sum()),
                     "n_publicaciones": s.Archivo_Origen.nunique(), "n_cuentas_distintas": s.cuenta_etiqueta.nunique(),
                     "cumple_umbral_3_publicaciones_de_cuentas_distintas": bool(s.Archivo_Origen.nunique() >= 3 and s.cuenta_etiqueta.nunique() >= 3),
                     "n_filas_con_texto_de_referencia": int(con_texto[d.index].sum())})
pd.DataFrame(rows).to_csv("conteos_de_recuperacion.csv", index=False, encoding="utf-8-sig")
pp = I.groupby("Archivo_Origen")[cols].sum().astype(int); pp.insert(0, "n_filas_con_texto", I.groupby("Archivo_Origen").apply(lambda g: int(con_texto[g.index].sum())))
pp.reset_index().to_csv("conteos_por_publicacion.csv", index=False, encoding="utf-8-sig")
print("filas:", len(I), "| con texto:", int(con_texto.sum()), "| con algún repertorio:", int((I.n_repertorios > 0).sum()), "| sin recuperación:", int(I.sin_recuperacion.sum()))
