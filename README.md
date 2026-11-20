# Repertorios del castigo

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23557846.svg)](https://doi.org/10.5281/zenodo.23557846)

**Scripts de armonización y análisis de un corpus de comentarios en Facebook, Instagram y TikTok sobre
un caso de castigo extralegal en Colombia (diciembre de 2025).**

Este repositorio acompaña un estudio cualitativo sobre cómo se legitima discursivamente un castigo
extralegal ya consumado en la conversación pública en redes sociales, y hacia qué nuevos blancos se
desplaza la demanda de castigo. Contiene el código que transforma las exportaciones crudas en las
bases analíticas usadas en el artículo. **No contiene datos** (ver [Datos](#datos)).

## Contenido

```
repertorios-del-castigo/
├── scripts/
│   ├── build_corpus.py          armonizador: normaliza plataforma, fechas, tipos e identificadores,
│   │                            reconstruye respuestas y marca duplicados (solo librería estándar)
│   ├── generar_bases.py         ejecuta build_corpus.py y escribe las tres bases en Excel
│   │                            (FB+IG, TikTok, y las tres plataformas juntas) + inventarios
│   ├── generar_registro.py      registro de publicaciones: texto, cuenta, tipo de cuenta,
│   │                            formato, control de fecha y transcripción
│   ├── transcribir_videos.py    transcripción del audio de videos con faster-whisper
│   └── analisis/
│       ├── etapa0_base_analitica.py   base analítica (hora de Colombia, ventanas, tipo de cuenta)
│       │                              y verificación de 48 cifras
│       ├── etapa1_figuras.py          figuras descriptivas (n absolutos, sin pruebas estadísticas)
│       ├── etapa2_recuperacion.py     recuperación léxica por repertorio
│       └── etapa3_marco_muestreo.py   marco de muestreo intencional y orden de lectura
├── lexico/
│   ├── lexico_tematico.json         léxico exploratorio del dashboard (6 dimensiones y 4 encuadres)
│   └── lexico_repertorios_v1.4.json léxico de recuperación por repertorio (12 repertorios)
├── docs/
│   ├── diccionario_variables.md las 31 columnas de las bases
│   └── recoleccion.md           cómo se recolectaron los datos y sus límites
└── datos/
    └── README.md                estructura esperada de los datos (no publicados)
```

## Uso

Requiere Python 3.10 o superior.

```
pip install -r requirements.txt
python scripts/generar_bases.py --datos datos/bases_armonizadas
python scripts/generar_registro.py --datos datos/bases_armonizadas
python scripts/transcribir_videos.py video1.mp4 video2.mp4
```

Scripts de análisis (se ejecutan desde una carpeta de trabajo; leen las bases de `datos/bases_armonizadas`
o de la carpeta indicada en la variable `EXODOXA_DATOS`, y escriben sus salidas en la carpeta actual):

```
python scripts/analisis/etapa0_base_analitica.py
python scripts/analisis/etapa2_recuperacion.py lexico/lexico_repertorios_v1.4.json
python scripts/analisis/etapa3_marco_muestreo.py
python scripts/analisis/etapa1_figuras.py
```

`etapa1_figuras.py` excluye nombres de personas de las figuras de términos con una lista local
(`terminos_excluidos_nombres.txt`) que **no se publica**; sin ella, el script avisa qué términos revisar.
Sus salidas (base analítica, índices, muestra) contienen datos del corpus y no deben publicarse.

`build_corpus.py` también puede usarse solo:

```
python scripts/build_corpus.py --raw-dir CARPETA_DE_CSV --output-dir SALIDA
```

## Datos

Las bases contienen nombres y usuarios públicos de quienes comentaron, y el caso involucra a menores
de edad. Por eso **no se publican**, de acuerdo con la Ley Estatutaria 1581 de 2012 de protección
de datos personales (Colombia) y con las condiciones de uso de las plataformas. Una versión
anonimizada está disponible a solicitud razonable con fines de investigación.

La recolección se hizo con una herramienta propia de navegador que no forma parte de este
repositorio. Su funcionamiento y sus límites se describen en [docs/recoleccion.md](docs/recoleccion.md)
y en la metodología del artículo.

## Léxico

`lexico/lexico_repertorios_v1.4.json` es el léxico de recuperación usado para orientar la lectura en el
estudio: 12 repertorios definidos con expresiones regulares. Recupera candidatos para lectura; un
comentario recuperado no es un comentario codificado y sus conteos no son prevalencias.

`lexico/lexico_tematico.json` es una **herramienta exploratoria de recuperación**, no una codificación
validada. Las dimensiones marcadas como `solo_tema` detectan que se habla de un tema, no que el
fenómeno ocurra. En el estudio se usó para localizar segmentos de lectura, nunca para estimar
prevalencias.

## Cómo citar

ExoDoxa. (2026). *Repertorios del castigo: scripts de armonización y análisis de comentarios en Facebook, Instagram y TikTok* (Versión 1.1.0) [Software]. Zenodo. https://doi.org/10.5281/zenodo.24405677

El DOI 10.5281/zenodo.23557846 apunta siempre a la versión más reciente. Ver también [CITATION.cff](CITATION.cff).

## Licencia

Código bajo licencia [MIT](LICENSE).
