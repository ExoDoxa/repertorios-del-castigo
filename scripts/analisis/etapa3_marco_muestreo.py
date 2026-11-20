# -*- coding: utf-8 -*-
"""Etapa 3 — Marco de muestreo intencional y orden de lectura.
Entradas: corpus_analitico.parquet (Etapa 0) e indice_de_recuperacion.csv (Etapa 2, léxico v1.4).
Salidas:  muestra_intencional.csv  (450 comentarios, con el motivo de cada selección, sin texto ni usuarios)
          marco_estratos.csv       (población, cuota y composición de cada estrato)
Diseño: máxima variación por celda (plataforma × tipo de fuente × momento) mediante turnos entre celdas, con tope de comentarios por
publicación dentro de cada estrato; casos clave, casos negativos y estratos de no recuperados. Semilla fija. No es una muestra
probabilística: no sirve para estimar prevalencias. Uso: python etapa3_marco_muestreo.py
"""
import re, json
import numpy as np, pandas as pd

SEMILLA = 20261023
rng = np.random.default_rng(SEMILLA)
com = pd.read_parquet("corpus_analitico.parquet")
idx = pd.read_csv("indice_de_recuperacion.csv").drop(columns=["Plataforma", "Archivo_Origen", "es_respuesta"])
com = com.merge(idx, on="clave_comentario", how="left", validate="1:1")
RID = [f"R{i:02d}" for i in range(1, 13)]
NOMBRE = {"R01": "señalamiento y evidencia", "R02": "disputa de la culpabilidad", "R03": "legitimación del castigo ocurrido", "R04": "llamado a castigar, repetir o extender",
          "R05": "punitivismo legal", "R06": "referencia al agente", "R07": "nacionalidad y xenofobia", "R08": "duelo", "R09": "crítica al Estado",
          "R10": "rumor y circulación", "R11": "rechazo del castigo y compasión por el señalado", "R12": "responsabilización de los cuidadores (candidato)"}
com["arch"] = com["Archivo_Origen"].str.lower().str.replace(".csv", "", regex=False)

# --- variables del marco -------------------------------------------------------------------------------------------
grupo = {"medio nacional": "medio", "medio local o regional": "medio", "página de noticias sin redacción": "página sin redacción", "creador de contenido": "persona (creador, vidente, particular)",
         "vidente o esotérico": "persona (creador, vidente, particular)", "particular": "persona (creador, vidente, particular)", "otro": "otro o eliminada", "no determinado (publicación eliminada)": "otro o eliminada"}
com["tipo_grupo"] = com["tipo_cuenta"].map(grupo)
def momento(r):
    if r.Plataforma == "Instagram": return "IG " + str(r.ventana_ig)[:2]
    if r.Plataforma == "TikTok":
        dd = r.dia_cot if pd.notna(r.dia_cot) else r.post_dia_cot   # sin fecha propia: se usa el día de la publicación (solo para estratificar)
        d = dd.day
        return f"TT {d}-dic" if d <= 14 else "TT 15-dic o después"
    return "FB pub " + (r.post_dia_cot.strftime("%d-dic") if pd.notna(r.post_dia_cot) else "s/f")
com["momento"] = com.apply(momento, axis=1)
com["momento_imputado"] = (com.Plataforma == "TikTok") & com.dia_cot.isna()
com["celda"] = com["Plataforma"].str[:2] + " | " + com["tipo_grupo"] + " | " + com["momento"]
elegible = (~com.texto_vacio) & (~com.solo_emoji) & (com.n_palabras >= 3)
emoji_ok = (~com.texto_vacio) & com.solo_emoji
N_ELEG, N_EMOJI = int(elegible.sum()), int(emoji_ok.sum())

sel = {}      # índice -> dict(estrato, rep, motivo)
def disponible(mask): return com[mask & ~com.index.isin(list(sel))]
PLATS = ["Facebook", "Instagram", "TikTok"]; turno = {"k": 0}
def reparto(cuota, disp):
    """Reparto igual entre plataformas (el resto rota entre ellas); lo que una plataforma no puede aportar pasa a las demás."""
    base, resto = divmod(cuota, 3); q = {p: base for p in PLATS}
    for j in range(resto): q[PLATS[(turno["k"] + j) % 3]] += 1
    turno["k"] += resto
    for _ in range(10):
        falta = sum(max(0, q[p] - disp[p]) for p in PLATS)
        for p in PLATS: q[p] = min(q[p], disp[p])
        if falta == 0: break
        libres = [p for p in PLATS if disp[p] > q[p]]
        if not libres: break
        for j in range(falta): q[libres[j % len(libres)]] += 1
        for p in PLATS: q[p] = min(q[p], disp[p])
    return q
def tomar(pool, cuota, estrato, rep, motivo, plats=None):
    """Primero reparte la cuota por plataforma; dentro de cada plataforma, turnos entre celdas (de menor a mayor), con tope por publicación y azar con semilla."""
    disp = {p: (int((pool.Plataforma == p).sum()) if plats is None or p in plats else 0) for p in PLATS}; q = reparto(cuota, disp); n = 0
    for p in PLATS:
        sub = pool[pool.Plataforma == p]; cupo = q[p]
        if cupo == 0: continue
        tope = max(1, int(np.ceil(cupo / 3)))
        celdas = {k: list(rng.permutation(g.index.values)) for k, g in sub.groupby("celda")}
        orden = sorted(celdas, key=lambda k: (len(celdas[k]), k)); por_pub = {}; elegidos = []
        while len(elegidos) < cupo and any(celdas.values()):
            avance = False
            for k in orden:
                if len(elegidos) >= cupo: break
                for pos, i in enumerate(celdas[k]):
                    a = com.at[i, "Archivo_Origen"]
                    if por_pub.get(a, 0) < tope: por_pub[a] = por_pub.get(a, 0) + 1; elegidos.append(i); celdas[k].pop(pos); avance = True; break
            if not avance: tope += 1
        for i in elegidos: sel[i] = {"estrato": estrato, "repertorio": rep, "motivo": motivo}
        n += len(elegidos)
    return n

# 1) casos clave -------------------------------------------------------------------------------------------------------
clave = []
for p in ["Facebook", "Instagram", "TikTok"]:
    d = disponible(elegible & (com.Plataforma == p) & ~com.es_respuesta).sort_values("Likes_Comentario", ascending=False).head(3)
    for i in d.index: sel[i] = {"estrato": "clave", "repertorio": "", "motivo": f"Clave: de los 3 comentarios con más me gusta en {p} (nivel 0, ≥3 palabras)"}
ig = com[(com.Plataforma == "Instagram") & ~com.texto_vacio].copy(); ig["min"] = ig.fecha_cot_ig.dt.floor("min")
muerte = re.compile(r"mataron|\bmuri|muerto|asesinaron|decapit|lo mat|desviv")
hitos = {}
for etq, ts in [("primer comentario de Instagram que alude a la muerte (12:06)", "2025-12-11 12:06"), ("primer comentario de Instagram que la afirma (13:33)", "2025-12-11 13:33")]:
    c = ig[(ig["min"] == pd.Timestamp(ts, tz="America/Bogota")) & ig.texto_norm.str.contains(muerte)]
    hitos[etq] = len(c)
    if len(c) and c.index[0] not in sel: sel[c.index[0]] = {"estrato": "clave", "repertorio": "", "motivo": "Clave: " + etq}
r7 = com[elegible & com.R07 & ~com.index.isin(list(sel))]
f7 = r7[r7.Plataforma == "Facebook"].copy(); f7["u"] = rng.random(len(f7))
for i in f7.sort_values(["post_dia_cot", "u"]).head(3).index: sel[i] = {"estrato": "clave", "repertorio": "R07", "motivo": "Clave: de los 3 comentarios de Facebook con marca de nacionalidad en las publicaciones más tempranas (la fecha del comentario es semanal)"}
for i in r7[r7.Plataforma == "Instagram"].sort_values("fecha_cot_ig").head(3).index: sel[i] = {"estrato": "clave", "repertorio": "R07", "motivo": "Clave: de los 3 primeros comentarios de Instagram con marca de nacionalidad"}
t7 = r7[(r7.Plataforma == "TikTok") & r7.dia_cot.notna()].copy(); t7["u"] = rng.random(len(t7))
for i in t7.sort_values(["dia_cot", "u"]).head(3).index: sel[i] = {"estrato": "clave", "repertorio": "R07", "motivo": "Clave: de los 3 primeros comentarios de TikTok con marca de nacionalidad (por día)"}
for i in disponible(elegible & ~com.es_respuesta).sort_values("Respuestas_Comentario", ascending=False).head(2).index:
    sel[i] = {"estrato": "clave", "repertorio": "", "motivo": "Clave: de los 2 comentarios con más respuestas declaradas (nivel 0, ≥3 palabras)"}
# 2) casos negativos (aproximación declarada: la postura de las 45 publicaciones se codifica en la Etapa 4) -------------------
afirman = ["face6", "inst6", "inst11", "inst9"]; disputan = ["tt15", "tt19", "tiktok3", "tt17", "tiktok2"]
tomar(disponible(elegible & com.R02 & com.arch.isin(afirman)), 20, "negativo_1", "R02", "Negativo: disputa de la culpabilidad (R02) bajo publicaciones que, por su texto, señalan o afirman la culpabilidad (con «presunto»)")
tomar(disponible(elegible & com.R03 & com.arch.isin(disputan)), 20, "negativo_2", "R03", "Negativo: legitimación del castigo (R03) bajo publicaciones que, por su transcripción, discuten la culpabilidad")
# 3) sin ninguna recuperación ----------------------------------------------------------------------------------------------
tomar(disponible(elegible & com.sin_recuperacion), 85, "sin_recuperacion", "", "Sin ninguna recuperación léxica: máxima variación por celda")
# 4) no recuperados por repertorio ---------------------------------------------------------------------------------------------
for R in RID: tomar(disponible(elegible & ~com[R] & ~com.sin_recuperacion), 6, "no_recuperado_" + R, R, f"No recuperado por {R} ({NOMBRE[R]}), sí por otro repertorio")
# 5) recuperados por repertorio ---------------------------------------------------------------------------------------------------
for R in RID: tomar(disponible(elegible & com[R]), 18, "recuperado_" + R, R, f"Recuperado por {R} ({NOMBRE[R]}): máxima variación por celda")
# 6) solo emojis ------------------------------------------------------------------------------------------------------------------
tomar(disponible(emoji_ok), 15, "solo_emoji", "", "Solo emojis o signos: se leen pocos para describirlos (no entran al análisis de repertorios)", plats=["Instagram", "TikTok"])

# --- tabla de la muestra y orden de lectura por lotes de 30 --------------------------------------------------------------------------
M = com.loc[list(sel)].copy()
for k in ("estrato", "repertorio", "motivo"): M[k] = [sel[i][k] for i in M.index]
cuota_estrato = M.groupby("estrato").size()
M["u"] = rng.random(len(M)); M["rango"] = M.groupby("estrato")["u"].rank(method="first") - 1
M["puntaje"] = (M["rango"] + rng.random(len(M))) / M["estrato"].map(cuota_estrato)
M = M.sort_values("puntaje").reset_index().rename(columns={"index": "indice_corpus"})
M["orden_lectura"] = np.arange(1, len(M) + 1); M["lote"] = (M["orden_lectura"] - 1) // 30 + 1; M["orden_en_lote"] = (M["orden_lectura"] - 1) % 30 + 1
M["segunda_lectura"] = False
for k, g in M.groupby("lote"):
    n2 = 5 if k % 2 == 1 and k <= 15 else 4
    M.loc[rng.choice(g.index.values, size=min(n2, len(g)), replace=False), "segunda_lectura"] = True
M["repertorios_recuperados"] = M[RID].apply(lambda r: " ".join(x for x in RID if r[x]), axis=1)
cols = ["orden_lectura", "lote", "orden_en_lote", "clave_comentario", "Plataforma", "Archivo_Origen", "cuenta_etiqueta", "tipo_cuenta", "tipo_grupo", "momento", "es_respuesta",
        "n_palabras", "estrato", "repertorio", "motivo", "celda", "sin_recuperacion", "repertorios_recuperados", "postura_solo_caption", "momento_imputado", "segunda_lectura"]
M[cols].rename(columns={"repertorio": "repertorio_que_motiva"}).to_csv("muestra_intencional.csv", index=False, encoding="utf-8-sig")

# --- marco por estrato: población disponible, cuota y composición -------------------------------------------------------------------------
def grupo_de(e):
    if e.startswith("recuperado_"): return elegible & com[e[-3:]]
    if e.startswith("no_recuperado_"): return elegible & ~com[e[-3:]]
    return {"sin_recuperacion": elegible & com.sin_recuperacion, "solo_emoji": emoji_ok, "clave": elegible, "negativo_1": elegible & com.R02 & com.arch.isin(afirman), "negativo_2": elegible & com.R03 & com.arch.isin(disputan)}[e]
filas = []
for e, g in M.groupby("estrato"):
    filas.append({"estrato": e, "poblacion_elegible_total": int(grupo_de(e).sum()), "n_seleccionados": len(g), "n_celdas": g.celda.nunique(), "n_publicaciones": g.Archivo_Origen.nunique(),
                  "n_cuentas": g.cuenta_etiqueta.nunique(), "FB": int((g.Plataforma == "Facebook").sum()), "IG": int((g.Plataforma == "Instagram").sum()), "TT": int((g.Plataforma == "TikTok").sum()),
                  "respuestas": int(g.es_respuesta.sum())})
F = pd.DataFrame(filas).sort_values("estrato"); F.to_csv("marco_estratos.csv", index=False, encoding="utf-8-sig")
print(f"elegibles (≥3 palabras, no solo emoji): {N_ELEG} | solo emoji: {N_EMOJI} | seleccionados: {len(M)} | únicos: {M.clave_comentario.nunique()} | lotes: {M.lote.nunique()}")
print("hitos de Instagram hallados:", hitos)
print(F.to_string(index=False))
print("segunda lectura:", int(M.segunda_lectura.sum()), "| por plataforma:", M.Plataforma.value_counts().to_dict())
