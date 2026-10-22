# Repertorios del castigo

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
│   └── transcribir_videos.py    transcripción del audio de videos con faster-whisper
├── lexico/
│   └── lexico_tematico.json     léxico exploratorio (6 dimensiones y 4 encuadres)
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

`lexico/lexico_tematico.json` es una **herramienta exploratoria de recuperación**, no una codificación
validada. Las dimensiones marcadas como `solo_tema` detectan que se habla de un tema, no que el
fenómeno ocurra. En el estudio se usó para localizar segmentos de lectura, nunca para estimar
prevalencias.

## Cómo citar

Ver [CITATION.cff](CITATION.cff). Cada versión publicada tiene un DOI en Zenodo.

## Licencia

Código bajo licencia [MIT](LICENSE).
