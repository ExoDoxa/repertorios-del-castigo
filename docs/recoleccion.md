# Recolección de los datos

## Herramienta

Los comentarios se recolectaron con una extensión de Chrome de desarrollo propio (Manifest V3), que
no se publica. La extensión:

- trabaja sobre la página pública que la plataforma muestra en el navegador, con una sesión iniciada;
- carga los comentarios con desplazamiento automático, abre los hilos de respuestas, expande los
  textos truncados ("ver más") y, en Instagram, abre los comentarios ocultos por la plataforma;
- exporta cada publicación a un CSV con un esquema común de 22 columnas (comentario, autor, fecha,
  métricas, publicación de origen y procedencia de la extracción).

`scripts/build_corpus.py` lee esos CSV y los armoniza (ver `diccionario_variables.md`).

| Plataforma | Publicaciones | Extracción |
|---|---|---|
| Facebook | 15 (una eliminada después) | 15 y 16 de septiembre de 2026 |
| Instagram | 14 | 20 de octubre de 2026 |
| TikTok | 16 | 21 de octubre de 2026 |

## Verificación

- **Contra la página:** las cifras de cada publicación se compararon con lo que mostraba la plataforma.
- **Contra la API interna de la plataforma, una publicación por plataforma:**
  - Instagram: campo por campo, con coincidencia total en los 611 comentarios presentes en ambas fuentes.
  - TikTok: para comprobar que el contador de comentarios declarado no es alcanzable.

## Límites conocidos

- **Muestra intencional:** las publicaciones se eligieron a mano. No es una muestra aleatoria.
- **Cobertura parcial:** Instagram y TikTok dejan de entregar comentarios antes de su propio contador.
  La mediana de comentarios capturados frente a declarados es del 88% en Facebook, del 92% en
  Instagram y del 38% en TikTok.
- **Fechas de los comentarios:**
  - Instagram: exactas, con hora.
  - TikTok: exactas al día.
  - Facebook: aproximadas, con precisión de una semana.

  Las fechas de las publicaciones son exactas en las tres plataformas. Las horas están en UTC; en el
  análisis se convierten a hora de Colombia (UTC−5).
- **Respuestas de Facebook:** son inferidas, a partir de una mención inicial a quien comentó antes.
- **Identificadores sintéticos:** en Facebook y TikTok, `ID_Comentario` es un hash de autor y texto.
  La clave única es `ID_Post_Origen` + `ID_Comentario`.
- **No capturados:** los comentarios que son solo un GIF en Instagram (~1%).
- **Comentarios ocultos por Instagram:** están incluidos, pero no van marcados.

## Registro de publicaciones

`scripts/generar_registro.py` construye una tabla por publicación a partir de lo que mostraba cada
página el 22 de octubre de 2026:

- texto de la publicación, cuenta y biografía;
- formato;
- control de fecha;
- transcripción, de dos fuentes:
  - los subtítulos automáticos de TikTok;
  - `transcribir_videos.py` (faster-whisper) para los videos sin subtítulos.

El **tipo de cuenta** es una propuesta, revisada a mano contra la biografía o la página de
información de cada cuenta.
