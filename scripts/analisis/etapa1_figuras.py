# -*- coding: utf-8 -*-
"""Etapa 1 (versión 2) — Figura 1 (cuerpo) y figuras descriptivas del Anexo (A1–A6), en formato APA.
Las imágenes contienen SOLO el gráfico (rótulos de ejes, encabezados de panel y leyendas). El rótulo «Figura N», el título y la
«Nota.» (n, fuente y límite) van en el Word que genera este mismo script (figuras_APA.docx), como pide APA.
Lee corpus_analitico.parquet (Etapa 0) y metricas_facebook_2026-10-22.csv. Todas las cifras son n absolutos; la figura A4 grafica
la tasa por 10.000 palabras con los conteos absolutos como etiqueta. Ninguna figura contiene pruebas estadísticas.
Los nombres de personas se excluyen de las figuras de términos con un archivo local `terminos_excluidos_nombres.txt` (NO se publica).
Uso: python etapa1_figuras.py
"""
import os, re, textwrap, json
import numpy as np, pandas as pd
import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import FuncFormatter, MaxNLocator, FixedLocator, NullLocator
from matplotlib.patches import Patch

DATA_DIR = os.environ.get("EXODOXA_DATOS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "datos", "bases_armonizadas"))
FB_METRICAS = os.path.join(DATA_DIR, "Facebook_Instagram", "metricas_facebook_2026-10-22.csv")
CORPUS = "corpus_analitico.parquet"
EXCLUIR = "terminos_excluidos_nombres.txt"
OUT, TAB, DPI = "figuras", "tablas_anexo", 300
os.makedirs(OUT, exist_ok=True); os.makedirs(TAB, exist_ok=True)

# ---- estilo: escalera de tamaños (8/7/6,5), color fijo por plataforma con luminosidades separadas (legible en escala de grises) ----
mpl.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "axes.titlesize": 8.5, "axes.labelsize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlelocation": "left", "axes.titleweight": "regular", "figure.dpi": 120, "savefig.dpi": DPI, "axes.linewidth": 0.6,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6})
PLAT = ["Facebook", "Instagram", "TikTok"]
COL = {"Facebook": "#08519C", "Instagram": "#F1A7C8", "TikTok": "#2E9E5B"}      # azul oscuro, rosa claro, verde medio (gris 68 / 193 / 117)
EDG = {"Facebook": "#041E3F", "Instagram": "#A23A6E", "TikTok": "#124D2A"}      # versión oscura para bordes, anillos y rayados
TIPO_ORDEN = ["medio nacional", "medio local o regional", "página de noticias sin redacción", "creador de contenido",
              "vidente o esotérico", "particular", "otro", "no determinado (publicación eliminada)"]
# tipos de cuenta: sin azul, rosa ni verde (reservados a las plataformas); el rayado distingue los que se parecen en gris
TIPO_EST = {"medio nacional": ("#1A1A1A", ""), "medio local o regional": ("#C9C9C9", "///"), "página de noticias sin redacción": ("#E69F00", ""),
            "creador de contenido": ("#D55E00", ""), "vidente o esotérico": ("#F0E442", "xx"), "particular": ("#8C510A", ""),
            "otro": ("#FFFFFF", "..."), "no determinado (publicación eliminada)": ("#FFFFFF", "")}

def fn(x): return f"{x:,.0f}".replace(",", ".")
def fp(x, d=1): return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
fmt_n = FuncFormatter(lambda x, _: fn(x))
def panel(ax, letter): ax.text(-0.02, 1.03, letter, transform=ax.transAxes, fontsize=10, fontweight="bold", va="bottom", ha="right")
def code(a): return a.replace(".csv", "")
CAPS = {}                       # nombre de archivo -> {"titulo":..., "nota":...}
PROBLEMAS = []

def revisar(fig, nombre):
    """Revisión geométrica: textos que se superponen o que salen del lienzo (se ignoran las marcas de eje fuera de la vista)."""
    fig.canvas.draw(); r = fig.canvas.get_renderer(); ocultos = set()
    for ax in fig.axes:
        for eje, (lo, hi) in ((ax.xaxis, sorted(ax.get_xlim())), (ax.yaxis, sorted(ax.get_ylim()))):
            for tk in eje.get_major_ticks() + eje.get_minor_ticks():
                if not (lo - 1e-9 <= tk.get_loc() <= hi + 1e-9): ocultos.update([tk.label1, tk.label2])
    ts = [(t, t.get_window_extent(r)) for t in fig.findobj(mpl.text.Text) if t.get_text().strip() and t.get_visible() and t not in ocultos]
    for i, (a, ba) in enumerate(ts):
        if ba.x0 < -1 or ba.y0 < -1 or ba.x1 > fig.bbox.x1 + 1 or ba.y1 > fig.bbox.y1 + 1:
            PROBLEMAS.append(f"{nombre}: fuera del lienzo → {a.get_text()[:40]!r}")
        for b, bb in ts[i + 1:]:
            if ba.overlaps(bb) and not (ba.width < 2 or bb.width < 2): PROBLEMAS.append(f"{nombre}: se pisan {a.get_text()[:28]!r} y {b.get_text()[:28]!r}")
def cerrar(fig, nombre, titulo, nota, left=0.1, right=0.985, top=0.95, extra_in=0.5, leyenda=None, leyenda_in=0.0):
    """Guarda SOLO el gráfico. Título y nota se registran para el Word."""
    H = fig.get_size_inches()[1]
    fig.subplots_adjust(left=left, right=right, top=top, bottom=(leyenda_in + extra_in) / H)
    if leyenda: fig.legend(loc="lower center", frameon=False, bbox_to_anchor=(0.5, 0.06 / H), **leyenda)
    revisar(fig, nombre); fig.savefig(f"{OUT}/{nombre}.png"); plt.close(fig)
    CAPS[nombre] = {"titulo": titulo, "nota": nota}

com = pd.read_parquet(CORPUS)
P = (com.groupby("Archivo_Origen").agg(plat=("Plataforma", "first"), filas=("clave_comentario", "size"), comentarios=("es_respuesta", lambda s: int((~s).sum())),
      respuestas=("es_respuesta", "sum"), tipo=("tipo_cuenta", "first"), etiqueta=("cuenta_etiqueta", "first"), post_fecha=("post_fecha_cot", "first"),
      decl_base=("Post_Comentarios_Total", "first"), eliminada=("post_eliminada", "first")).reset_index())
P["codigo"] = P["Archivo_Origen"].map(code)
fbm = pd.read_csv(FB_METRICAS)[["Archivo_Origen", "Comentarios_Declarados"]]
P = P.merge(fbm, on="Archivo_Origen", how="left")
P["declarados"] = np.where(P["plat"].eq("Facebook"), P["Comentarios_Declarados"], P["decl_base"])
P.loc[P["declarados"].eq(0), "declarados"] = np.nan

# =========================== FIGURA 1 (cuerpo) ======================================================================
def figura1():
    filas_y, y, cab = [], 0, []
    for p in PLAT:
        d = P[P.plat == p].sort_values("filas", ascending=False)
        cab.append((y, p, len(d), int(d.filas.head(3).sum()), int(d.filas.sum()))); y += 1
        for _, r in d.iterrows(): filas_y.append((y, r)); y += 1
        y += 0.6
    H = 0.158 * y + 2.0
    fig, ax = plt.subplots(figsize=(7.2, H))
    for yy, r in filas_y:
        c, h = TIPO_EST[r.tipo]
        ax.barh(yy, r.filas, color=c, hatch=h, edgecolor="#222222", linewidth=0.5, height=0.74, linestyle="--" if r.eliminada else "-")
        ax.text(r.filas, yy, " " + fn(r.filas), va="center", fontsize=6)
    ax.set_yticks([yy for yy, _ in filas_y])
    ax.set_yticklabels([("publicación de Facebook eliminada" if r.eliminada else f"{r.etiqueta} ({r.codigo})")[:46] for _, r in filas_y], fontsize=6)
    for yy, p, n, t3, tt in cab:
        ax.text(0, yy, "■", color=COL[p], fontsize=9, va="center", ha="left", path_effects=None)
        ax.text(P.filas.max() * 0.055, yy, f"{p}", fontsize=7.5, fontweight="bold", va="center", ha="left")
    ax.set_ylim(y - 0.4, -0.8); ax.tick_params(axis="y", length=0); ax.set_xlim(0, P.filas.max() * 1.12)
    ax.xaxis.set_major_formatter(fmt_n); ax.set_xlabel("Filas (comentarios y respuestas)")
    leg = dict(handles=[Patch(facecolor=TIPO_EST[t][0], hatch=TIPO_EST[t][1], edgecolor="#222222", linewidth=0.5, label=t.capitalize()) for t in TIPO_ORDEN],
               ncol=4, title="Tipo de cuenta que publica", title_fontsize=7, fontsize=6.5)
    tops = {p: (t3, tt) for _, p, _, t3, tt in cab}
    cerrar(fig, "figura1_peso_por_publicacion", "Peso de cada publicación en el corpus, por plataforma y tipo de cuenta",
           f"n = 45 publicaciones y 15.124 filas. Las tres publicaciones con más filas suman {fn(tops['Facebook'][0])} de {fn(tops['Facebook'][1])} en Facebook, {fn(tops['Instagram'][0])} de {fn(tops['Instagram'][1])} en Instagram y {fn(tops['TikTok'][0])} de {fn(tops['TikTok'][1])} en TikTok. Fuente: ExoDoxa (2026a, 2026b). Límite: muestra intencional; las cuentas anonimizadas se numeran y la misma persona conserva su número entre plataformas; el tipo de fuente está confundido con la plataforma.",
           left=0.40, right=0.97, top=0.995, extra_in=0.5, leyenda=leg, leyenda_in=0.62)
    P[["plat", "codigo", "etiqueta", "tipo", "filas", "comentarios", "respuestas"]].sort_values(["plat", "filas"], ascending=[True, False]).to_csv(f"{TAB}/figura1_filas_por_publicacion.csv", index=False, encoding="utf-8-sig")

# =========================== A1: volumen en el tiempo ==============================================================
def a1_volumen():
    TZ = "America/Bogota"
    ig = com[com.Plataforma == "Instagram"].dropna(subset=["fecha_cot_ig"])
    t0, t1 = pd.Timestamp("2025-12-10 18:00", tz=TZ), pd.Timestamp("2025-12-17 00:00", tz=TZ)
    ig_in = ig[(ig.fecha_cot_ig >= t0) & (ig.fecha_cot_ig < t1)]
    horas = ig_in.fecha_cot_ig.dt.floor("h").value_counts().sort_index()
    tt = com[(com.Plataforma == "TikTok") & com.Fecha_Precision.eq("day")]
    dias = tt.dia_cot.value_counts().sort_index(); dias_in = dias[(dias.index >= "2025-12-11") & (dias.index <= "2025-12-16")]
    f = P[P.plat == "Facebook"].sort_values("post_fecha"); xf = pd.to_datetime(f.post_fecha, utc=True).dt.tz_convert(TZ)
    fig, ax = plt.subplots(3, 1, figsize=(7.2, 6.2), gridspec_kw={"hspace": 0.62})
    a = ax[0]; a.bar(horas.index, horas.values, width=1 / 24 * 0.92, color=COL["Instagram"], edgecolor=EDG["Instagram"], linewidth=0.3, align="edge")
    a.set_xlim(t0, t1); a.set_ylabel("Comentarios por hora"); a.yaxis.set_major_formatter(fmt_n); a.set_title("Instagram, por hora")
    pk = horas.idxmax(); a.annotate(f"máximo: {horas.max()} en una hora", (pk + pd.Timedelta(minutes=30), horas.max()), xytext=(10, -2), textcoords="offset points", fontsize=6.5, va="top")
    b = ax[1]; x = pd.to_datetime(dias_in.index); b.bar(x, dias_in.values, width=0.92, align="edge", color=COL["TikTok"], edgecolor=EDG["TikTok"], linewidth=0.4)
    for xi, v in zip(x, dias_in.values): b.text(xi + pd.Timedelta(hours=11), v, fn(v), ha="center", va="bottom", fontsize=6.5)
    b.set_xlim(t0.tz_localize(None), t1.tz_localize(None)); b.set_ylabel("Comentarios por día"); b.yaxis.set_major_formatter(fmt_n); b.set_ylim(0, dias_in.max() * 1.2); b.set_title("TikTok, por día")
    c = ax[2]; c.vlines(xf, 0, f.filas, color=COL["Facebook"], linewidth=1.0)
    c.scatter(xf[~f.eliminada], f.filas[~f.eliminada], s=20, color=COL["Facebook"], edgecolor=EDG["Facebook"], linewidth=0.4, zorder=3)
    c.scatter(xf[f.eliminada], f.filas[f.eliminada], s=20, facecolor="white", edgecolor=COL["Facebook"], zorder=3)
    for xx, r in zip(xf, f.itertuples()):
        if r.filas > 1000: c.annotate(r.codigo, (xx, r.filas), xytext=(5, 2), textcoords="offset points", fontsize=6.5)
    c.set_xlim(t0, t1); c.set_ylabel("Filas por publicación"); c.yaxis.set_major_formatter(fmt_n); c.set_ylim(0, f.filas.max() * 1.18)
    c.set_title("Facebook, por fecha de publicación"); c.text(0.99, 0.92, "círculo vacío: publicación eliminada", transform=c.transAxes, ha="right", fontsize=6.5)
    for axx, lab in zip(ax, "abc"): panel(axx, lab)
    for axx in (ax[0], ax[2]):
        axx.xaxis.set_major_locator(mdates.DayLocator(tz=TZ)); axx.xaxis.set_major_formatter(mdates.DateFormatter("%d-dic", tz=TZ))
    ax[1].xaxis.set_major_locator(mdates.DayLocator()); ax[1].xaxis.set_major_formatter(mdates.DateFormatter("%d-dic"))
    ig_tail = int((ig.fecha_cot_ig >= t1).sum()); ig_jan = int((ig.fecha_cot_ig >= pd.Timestamp("2026-01-01", tz=TZ)).sum())
    cerrar(fig, "A1_volumen_en_el_tiempo", "Volumen de comentarios en el tiempo: Instagram por hora, TikTok por día y Facebook por fecha de publicación",
           f"Instagram (panel a): n = {fn(len(ig_in))} de {fn(len(ig))} comentarios con hora, en hora de Colombia. TikTok (panel b): n = {fn(dias_in.sum())} de {fn(len(tt))} comentarios con día, que es el que entrega la plataforma, con zona horaria desconocida. Facebook (panel c): {len(f)} publicaciones, n = {fn(f.filas.sum())} filas, ubicadas por su fecha de publicación porque las fechas de sus comentarios tienen precisión de una semana. Quedan fuera de las series: en Instagram, {ig_tail} comentarios desde el 17 de diciembre ({ig_jan} desde el 1 de enero, casi todos en una sola publicación); en TikTok, {fn(len(tt) - dias_in.sum())} filas con día fuera del 11–16 de diciembre y 96 sin fecha o con fecha aproximada. Fuente: ExoDoxa (2026a). Límite: el volumen depende de qué publicaciones se capturaron y de la cobertura (mediana de TikTok, 37,5%); no es comparable entre plataformas.",
           left=0.095, right=0.975, top=0.955, extra_in=0.4)
    horas.rename("comentarios").to_csv(f"{TAB}/A1_instagram_por_hora_cot.csv", encoding="utf-8-sig"); dias.rename("comentarios").to_csv(f"{TAB}/A1_tiktok_por_dia.csv", encoding="utf-8-sig")

# =========================== A2: cobertura capturados / declarados ================================================
def a2_cobertura():
    d = P.dropna(subset=["declarados"]).copy(); d["declarados"] = d["declarados"].astype(float)
    fig, axes = plt.subplots(3, 1, figsize=(7.2, 7.0), gridspec_kw={"height_ratios": [14, 14, 16], "hspace": 0.42}, sharex=True)
    for ax, p in zip(axes, PLAT):
        e = d[d.plat == p].sort_values("declarados", ascending=False).reset_index(drop=True)
        ax.hlines(e.index, e.filas, e.declarados, color="#888888", linewidth=0.8, zorder=1)
        ax.scatter(e.declarados, e.index, s=46, facecolor="white", edgecolor=EDG[p], linewidth=1.2, zorder=2)
        ax.scatter(e.filas, e.index, s=16, color=COL[p], edgecolor=EDG[p], linewidth=0.5, zorder=3)
        ax.set_yticks(e.index); ax.set_yticklabels(e.codigo, fontsize=6); ax.set_xscale("log"); ax.tick_params(axis="y", length=0)
        ax.set_title(p); ax.set_ylim(len(e) - 0.2, -0.8)
        ax.xaxis.set_major_locator(FixedLocator([20, 50, 100, 300, 1000, 3000])); ax.xaxis.set_minor_locator(NullLocator()); ax.xaxis.set_major_formatter(fmt_n)
        ax.tick_params(axis="x", labelbottom=True)
    axes[0].text(0.99, 0.08, "●  filas capturadas      ○  comentarios declarados por la plataforma", transform=axes[0].transAxes, fontsize=6.5, ha="right")
    axes[-1].set_xlabel("Comentarios (escala logarítmica)"); axes[-1].set_xlim(14, 7500)
    cerrar(fig, "A2_cobertura_capturados_declarados", "Comentarios capturados y declarados por la plataforma, por publicación",
           "n = 44 publicaciones con cifra declarada (Facebook 14, Instagram 14, TikTok 16); falta una publicación de Facebook eliminada. Fuente: ExoDoxa (2026a); las cifras declaradas de Facebook proceden de las métricas leídas el 22 de octubre de 2026 (la extracción fue el 15 y 16 de septiembre) y las de Instagram y TikTok son las declaradas al extraer. Ninguna cifra declarada de Facebook está marcada como aproximada en la fuente (sí lo están algunas reacciones, que aquí no se usan). Límite: control de calidad de los datos, no una medida del discurso; las cifras de Facebook, leídas cinco semanas después, pueden haber cambiado.",
           left=0.1, right=0.975, top=0.97, extra_in=0.5)
    d[["plat", "codigo", "filas", "declarados"]].rename(columns={"filas": "capturadas"}).to_csv(f"{TAB}/A2_cobertura.csv", index=False, encoding="utf-8-sig")

# =========================== A3 y A4: términos ===================================================================
STOP = set("""a al algo algunas algunos ante antes aqui aquí asi así aun aún aunque bien cada casi como con contra cual cuando de del desde donde dos el ella ellas ello ellos en entre era eran es esa esas ese eso esos esta estas este esto estos fue fueron ha había habia han hasta hay la las le les lo los mas más me mi mis mucho muy nada ni no nos nuestro o otra otras otro otros para pero poco por porque pues que qué se sea si sí sido sin sobre solo sólo son soy su sus también tambien tan te tengo ti todo todos tu tus un una uno unos usted ustedes va vamos van ver vez voy y ya yo ser está estoy están estamos tiene tienen tener hacer hace hizo puede pueden pueda ahora aquel cuanto cuantos nunca siempre ahi ahí allí alli dice dicen decir quien quién quienes cuáles cómo cuándo dónde ojalá""".split())
RE_TOK = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,}")
def cap_ratio(d):
    """Proporción de apariciones con mayúscula inicial fuera de inicio de frase (solo para revisión humana)."""
    cap, tot = {}, {}
    for s_ in d.Texto_Comentario.astype(str):
        for m in RE_TOK.finditer(s_):
            w = m.group(0); k = w.lower(); prev = s_[:m.start()].rstrip(); inicio = (not prev) or prev[-1] in ".!?¿¡\n…"
            tot[k] = tot.get(k, 0) + 1
            if w[0].isupper() and not w.isupper() and not inicio: cap[k] = cap.get(k, 0) + 1
    return {k: cap.get(k, 0) / n for k, n in tot.items() if n >= 5}
def conteo_terminos():
    d = com[~com.texto_vacio][["Plataforma", "ID_Post_Origen", "Texto_Comentario"]].copy()
    excl = set(open(EXCLUIR, encoding="utf-8").read().split()) if os.path.exists(EXCLUIR) else set()
    d["tok"] = d.Texto_Comentario.map(lambda s_: [t for t in (x.lower() for x in RE_TOK.findall(str(s_))) if t not in STOP and t not in excl])
    e = d.explode("tok").dropna(subset=["tok"])
    T = pd.concat([e.groupby(["Plataforma", "tok"]).size().rename("n"), e.groupby(["Plataforma", "tok"])["ID_Post_Origen"].nunique().rename("pubs")], axis=1).reset_index()
    return T, e.groupby("Plataforma").size(), d.groupby("Plataforma")["ID_Post_Origen"].nunique(), len(excl), cap_ratio(d)
def a3_frecuentes(T, tot, npub):
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 4.4), gridspec_kw={"wspace": 0.5}); out = []
    for ax, p in zip(axes, PLAT):
        e = T[T.Plataforma == p].sort_values("n", ascending=False).head(15).iloc[::-1].reset_index(drop=True); out.append(e)
        ax.barh(e.index, e.n, color=COL[p], edgecolor=EDG[p], linewidth=0.4, height=0.72); ax.set_yticks(e.index); ax.set_yticklabels(e.tok, fontsize=7); ax.tick_params(axis="y", length=0)
        for i, (v, k) in enumerate(zip(e.n, e.pubs)): ax.text(v, i, f" {fn(v)} · {k} pub.", va="center", fontsize=6)
        ax.set_xlim(0, e.n.max() * 1.65); ax.xaxis.set_major_formatter(fmt_n); ax.xaxis.set_major_locator(MaxNLocator(3))
        ax.set_title(p); ax.set_xlabel("Apariciones")
    cerrar(fig, "A3_terminos_frecuentes", "Términos más frecuentes en los comentarios de cada plataforma",
           f"n = 15.081 comentarios con texto: {fn(tot['Facebook'])} palabras en 15 publicaciones de Facebook, {fn(tot['Instagram'])} en 14 de Instagram y {fn(tot['TikTok'])} en 16 de TikTok. Se cuentan apariciones de palabras de 3 o más letras, sin palabras vacías (artículos, preposiciones, pronombres) ni nombres de personas; «pub.» indica en cuántas publicaciones de la plataforma aparece la palabra. La escala del eje cambia por plataforma. Fuente: ExoDoxa (2026a). Límite: tokenización simple, sin lematizar; pocas publicaciones concentran el volumen.",
           left=0.08, right=0.985, top=0.93, extra_in=0.5)
    pd.concat(out).to_csv(f"{TAB}/A3_terminos_frecuentes.csv", index=False, encoding="utf-8-sig")
def a4_caracteristicos(T, tot, npub):
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 5.0), gridspec_kw={"wspace": 0.7}); out = []
    for ax, p in zip(axes, PLAT):
        a = T[T.Plataforma == p].set_index("tok"); o = T[T.Plataforma != p].groupby("tok").n.sum()
        a["otras"] = o.reindex(a.index).fillna(0); a = a[(a.n >= 20) & (a.pubs >= 3)].copy()
        otros_tot = tot.sum() - tot[p]
        a["tasa_plat"] = a.n / tot[p] * 1e4; a["tasa_otras"] = a.otras / otros_tot * 1e4
        a["razon"] = (a.n / tot[p]) / ((a.otras + 1) / otros_tot)
        e = a.sort_values("razon", ascending=False).head(12).iloc[::-1].reset_index(); out.append(e.assign(plataforma=p))
        assert (e.tasa_plat > e.tasa_otras).all()      # la barra de color nunca queda por debajo de la gris
        y = np.arange(len(e)); ax.barh(y + 0.19, e.tasa_plat, height=0.36, color=COL[p], edgecolor=EDG[p], linewidth=0.4)
        ax.barh(y - 0.19, e.tasa_otras, height=0.36, color="white", hatch="////", edgecolor="#555555", linewidth=0.5)
        ax.set_yticks(y); ax.set_yticklabels(e.tok, fontsize=7); ax.tick_params(axis="y", length=0)
        for i, r in e.iterrows(): ax.text(r.tasa_plat, i + 0.19, f" n = {fn(r.n)} · {r.pubs}/{npub[p]} pub.", va="center", fontsize=5.6)
        for i, r in e.iterrows(): ax.text(r.tasa_otras, i - 0.19, f" n = {fn(r.otras)}", va="center", fontsize=5.6, color="#444444")
        ax.set_xlim(0, e.tasa_plat.max() * 2.35); ax.xaxis.set_major_locator(MaxNLocator(3))
        ax.set_title(p); ax.set_xlabel("Tasa por 10.000 palabras")
    leg = dict(handles=[Patch(facecolor="#777777", edgecolor="#333333", label="barra de color: en la plataforma"), Patch(facecolor="white", hatch="////", edgecolor="#555555", label="barra rayada: en las otras dos plataformas")], ncol=2, fontsize=6.5)
    cerrar(fig, "A4_terminos_caracteristicos", "Términos característicos de cada plataforma: tasa por 10.000 palabras frente a las otras dos",
           f"Términos con 20 o más apariciones y presentes en 3 o más publicaciones de la plataforma, sin nombres de personas. Las barras muestran la tasa por 10.000 palabras (apariciones divididas por las palabras de la plataforma, o de las otras dos juntas, por 10.000); los términos se ordenan por la razón entre ambas tasas, que es un criterio de orden y no una prueba. Las etiquetas dan los conteos absolutos (n) y las publicaciones donde aparece el término («k/m pub.», de las m de la plataforma). Palabras: Facebook {fn(tot['Facebook'])}, Instagram {fn(tot['Instagram'])}, TikTok {fn(tot['TikTok'])}; n = 15.081 comentarios con texto. Fuente: ExoDoxa (2026a). Límite: lo característico de una plataforma está confundido con las publicaciones y con el tipo de cuenta que las publica.",
           left=0.115, right=0.985, top=0.95, extra_in=0.5, leyenda=leg, leyenda_in=0.28)
    pd.concat(out).to_csv(f"{TAB}/A4_terminos_caracteristicos.csv", index=False, encoding="utf-8-sig")

# =========================== A5: textos repetidos entre publicaciones ============================================
def a5_repetidos():
    r = com[com.texto_repetido_entre_posts & ~com.texto_vacio]
    g = r.groupby("texto_norm").agg(filas=("clave_comentario", "size"), pubs=("ID_Post_Origen", "nunique"), plats=("Plataforma", "nunique"),
                                    autores=("Usuario_Arroba", "nunique"), emoji=("solo_emoji", "first"), pal=("n_palabras", "first"))
    g["tipo"] = np.where(g.emoji, "Solo emojis o signos", np.where(g.pal <= 2, "1–2 palabras", "3 o más palabras"))
    orden = ["Solo emojis o signos", "1–2 palabras", "3 o más palabras"]
    g["pubs_c"] = pd.cut(g.pubs, [1, 2, 3, 100], labels=["2 publicaciones", "3 publicaciones", "4 o más"])
    tab = g.groupby(["tipo", "pubs_c"], observed=False).size().unstack().reindex(orden)
    tab2 = g.groupby(["tipo", g.plats.map({1: "una plataforma", 2: "dos o tres plataformas", 3: "dos o tres plataformas"})], observed=False).size().unstack().reindex(orden)
    filas = g.groupby("tipo").filas.sum().reindex(orden); con_pal = g[~g.emoji]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.3), gridspec_kw={"wspace": 0.12}, sharey=True)
    ax = axes[0]; left = np.zeros(3)
    for c, s in zip(tab.columns, ["#D9D9D9", "#8C8C8C", "#2B2B2B"]):
        ax.barh(range(3), tab[c].fillna(0).values, left=left, color=s, edgecolor="white", linewidth=0.5, label=c); left += tab[c].fillna(0).values
    ax.set_yticks(range(3)); ax.set_yticklabels([f"{o}\n{int(left[i])} textos · {fn(filas.iloc[i])} filas" for i, o in enumerate(orden)]); ax.invert_yaxis()
    ax.set_xlim(0, 110); ax.set_xlabel("Textos distintos repetidos")
    ax.legend(frameon=False, loc="lower right", ncol=1, fontsize=6.5, title="Aparece en", title_fontsize=6.5)
    ax.set_title("Por número de publicaciones"); ax.tick_params(axis="y", length=0)
    ax = axes[1]; left = np.zeros(3)
    for c, s in zip(["una plataforma", "dos o tres plataformas"], ["#D9D9D9", "#2B2B2B"]):
        v = tab2[c].fillna(0).values; ax.barh(range(3), v, left=left, color=s, edgecolor="white", linewidth=0.5, label=c); left += v
    ax.set_xlim(0, 110); ax.set_xlabel("Textos distintos repetidos"); ax.tick_params(axis="y", length=0)
    ax.legend(frameon=False, loc="lower right", ncol=1, fontsize=6.5, title="Presente en", title_fontsize=6.5)
    ax.set_title("Por número de plataformas")
    for axx, lab in zip(axes, "ab"): panel(axx, lab)
    cerrar(fig, "A5_textos_repetidos_por_tipo", "Textos repetidos en dos o más publicaciones, por tipo de texto",
           f"n = {len(g)} textos distintos ({fn(g.filas.sum())} filas) que aparecen, tras pasar a minúsculas y quitar tildes, en 2 o más publicaciones; entre paréntesis del eje, textos y filas de cada tipo. Fuente: ExoDoxa (2026a). Límite: coincidencia exacta (no detecta variantes); repetir un texto no implica copia ni coordinación: {int((con_pal.autores >= 2).sum())} de los {len(con_pal)} textos con palabras los escribieron al menos 2 usuarios distintos. Los textos de solo emojis proceden de Instagram y TikTok: en la base casi no hay emojis de Facebook (Metodología, §1.6). No se reproducen los textos.",
           left=0.27, right=0.985, top=0.9, extra_in=0.6)
    tab.join(tab2).assign(filas=filas).to_csv(f"{TAB}/A5_textos_repetidos_por_tipo.csv", encoding="utf-8-sig")

# =========================== A6: tamaño del hilo (Instagram y TikTok) ===========================================
def a6_hilos():
    rows, extra = [], {}
    for p in ["Instagram", "TikTok"]:
        d = com[com.Plataforma == p]; rep = d[d.es_respuesta & d.Parent_Source.eq("explicit_id")]
        cnt = rep.groupby(["ID_Post_Origen", "ID_Comentario_Padre"]).size().rename("capturadas").reset_index()
        par = d[~d.es_respuesta][["ID_Post_Origen", "ID_Comentario", "Respuestas_Comentario"]].rename(columns={"ID_Comentario": "ID_Comentario_Padre", "Respuestas_Comentario": "declaradas"})
        t = cnt.merge(par, on=["ID_Post_Origen", "ID_Comentario_Padre"], how="inner"); t["plat"] = p; t["truncado"] = t.capturadas < t.declaradas; rows.append(t)
        m = par.merge(cnt, on=["ID_Post_Origen", "ID_Comentario_Padre"], how="left"); m["capturadas"] = m.capturadas.fillna(0)
        extra[p] = (int(((m.capturadas == 0) & (m.declaradas > 0)).sum()), len(cnt) - len(t))
    H = pd.concat(rows); bins = [0, 1, 2, 4, 9, 19, 10**6]; labs = ["1", "2", "3–4", "5–9", "10–19", "20 o más"]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.4), gridspec_kw={"wspace": 0.3}); res = {}
    for ax, p in zip(axes, ["Instagram", "TikTok"]):
        h = H[H.plat == p].copy(); h["cl"] = pd.cut(h.capturadas, bins, labels=labs)
        comp = h[~h.truncado].groupby("cl", observed=False).size().reindex(labs).fillna(0); trunc = h[h.truncado].groupby("cl", observed=False).size().reindex(labs).fillna(0)
        x = np.arange(len(labs)); ax.bar(x, comp.values, color=COL[p], edgecolor=EDG[p], linewidth=0.5, label="hilo completo (capturadas = declaradas)")
        ax.bar(x, trunc.values, bottom=comp.values, color="white", edgecolor=EDG[p], hatch="////", linewidth=0.8, label="hilo truncado (capturadas < declaradas)")
        for xi, (a, b) in enumerate(zip(comp.values, trunc.values)): ax.text(xi, a + b, f"{int(a + b)}", ha="center", va="bottom", fontsize=6.5)
        ax.set_xticks(x); ax.set_xticklabels(labs); ax.set_xlabel("Respuestas capturadas por comentario"); ax.set_ylabel("Comentarios con respuestas")
        ax.set_ylim(0, (comp + trunc).max() * 1.38); ax.yaxis.set_major_formatter(fmt_n); ax.set_title(p)
        ax.legend(frameon=False, loc="upper right", fontsize=6)
        res[p] = (len(h), int(h.capturadas.max()), int(h.truncado.sum()), int((h.declaradas - h.capturadas).clip(lower=0).sum()))
    for axx, lab in zip(axes, "ab"): panel(axx, lab)
    cerrar(fig, "A6_tamano_de_hilos", "Tamaño de los hilos de respuestas en Instagram y TikTok",
           f"Instagram (panel a): n = {res['Instagram'][0]} hilos, con un máximo de {res['Instagram'][1]} respuestas; {res['Instagram'][2]} truncados, a los que faltan {res['Instagram'][3]} respuestas. TikTok (panel b): n = {res['TikTok'][0]} hilos, con un máximo de {res['TikTok'][1]}; {res['TikTok'][2]} truncados, a los que faltan {res['TikTok'][3]}. Un hilo es un comentario con al menos una respuesta capturada con vínculo explícito. No se grafican {extra['Instagram'][0]} comentarios de Instagram y {extra['TikTok'][0]} de TikTok que declaran respuestas sin ninguna capturada, ni {extra['TikTok'][1]} respuesta de TikTok cuyo comentario no está en la base. Fuente: ExoDoxa (2026a). Límite: solo existen dos niveles (comentario y respuesta), por eso no se mide profundidad; Facebook queda fuera porque sus vínculos de respuesta son inferidos; los hilos truncados subestiman el tamaño real.",
           left=0.08, right=0.985, top=0.88, extra_in=0.55)
    H.groupby("plat").agg(hilos=("capturadas", "size"), maximo=("capturadas", "max"), truncados=("truncado", "sum")).to_csv(f"{TAB}/A6_resumen_hilos.csv", encoding="utf-8-sig")

# =========================== Word APA con rótulo, título y nota ===================================================
def construir_word():
    from apa_docx import ApaDoc
    A = ApaDoc(); A.h1("Figuras de la Metodología y del Anexo descriptivo")
    A.para("Cada figura lleva arriba su número (en negrita) y su título (en cursiva) y abajo su nota con n, fuente y límite. Las imágenes contienen solo el gráfico.", count=False, indent=False)
    orden = [("figura1_peso_por_publicacion", "Figura 1"), ("A1_volumen_en_el_tiempo", "Figura A1"), ("A2_cobertura_capturados_declarados", "Figura A2"),
             ("A3_terminos_frecuentes", "Figura A3"), ("A4_terminos_caracteristicos", "Figura A4"), ("A5_textos_repetidos_por_tipo", "Figura A5"), ("A6_tamano_de_hilos", "Figura A6")]
    for k, (nombre, rot) in enumerate(orden):
        A.figure(rot, CAPS[nombre]["titulo"], f"{OUT}/{nombre}.png", CAPS[nombre]["nota"], salto=(k < len(orden) - 1))
    A.save("figuras_APA.docx")

if __name__ == "__main__":
    figura1(); a1_volumen(); a2_cobertura()
    T, tot, npub, nexcl, capr = conteo_terminos(); a3_frecuentes(T, tot, npub); a4_caracteristicos(T, tot, npub)
    a5_repetidos(); a6_hilos()
    json.dump(CAPS, open(f"{TAB}/captions_figuras.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    try: construir_word()
    except ImportError as e: print("No se generó el Word (falta apa_docx.py o python-docx):", e)
    print("figuras:", sorted(os.listdir(OUT))); print("palabras por plataforma:", tot.to_dict(), "| términos excluidos por el archivo local:", nexcl)
    vistos = set(pd.read_csv(f"{TAB}/A3_terminos_frecuentes.csv").tok) | set(pd.read_csv(f"{TAB}/A4_terminos_caracteristicos.csv").tok)
    print("REVISAR (posibles nombres de persona en las figuras de términos):", sorted(t for t in vistos if capr.get(t, 0) >= 0.5) or "ninguno")
    print("revisión de solapes y recortes:", "sin problemas" if not PROBLEMAS else PROBLEMAS)
