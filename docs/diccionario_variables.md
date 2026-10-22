# Diccionario de variables

Las tres bases (FB+IG, TikTok y la conjunta) tienen las mismas 31 columnas en la hoja **Comentarios**.

| Columna | Descripción |
|---|---|
| `Plataforma` | Facebook, Instagram o TikTok. |
| `Tipo_Elemento` | Comentario o Respuesta según la plataforma. En Facebook las respuestas son INFERIDAS: mirar Nivel_Comentario. |
| `ID_Post_Origen` | Identificador de la publicación (Instagram: shortcode; Facebook: id o pfbid; TikTok: id del video). |
| `ID_Comentario` | Identificador del comentario. Instagram: nativo. Facebook (fb_…) y TikTok (tt_…): sintético, hash del texto y autor. |
| `ID_Comentario_Padre` | Comentario al que responde, si es una respuesta. |
| `Autor` | Nombre visible del autor. |
| `Usuario_Arroba` | Nombre de usuario (@). |
| `Texto_Comentario` | Texto del comentario. |
| `Fecha_Comentario` | Fecha del comentario. Con '~' delante es aproximada (calculada desde 'hace 2 d'). |
| `Fecha_Precision` | Precisión de la fecha del comentario. |
| `Likes_Comentario` | Me gusta del comentario. |
| `Respuestas_Comentario` | Respuestas que la plataforma declara para ese comentario. |
| `Nivel_Comentario` | 0 = comentario a la publicación, 1 = respuesta (incluye las inferidas de Facebook). |
| `Segundos_Desde_Post` | Segundos entre la publicación y el comentario (si ambas fechas son exactas). |
| `Post_Fecha` | Fecha de la publicación. |
| `Post_Likes` | Me gusta de la publicación (0 = no disponible u oculto por el autor). |
| `Post_Comentarios_Total` | Comentarios que declara la plataforma (no siempre alcanzable). |
| `Post_Shares` | Compartidos (si la plataforma lo muestra). |
| `Post_Views` | Reproducciones (no visibles en ninguna de las tres desde la web: 0). |
| `Ventana_Debate` | Tiempo entre el primer y el último comentario de esa extracción. |
| `URL_Origen` | Enlace de la publicación. |
| `ID_Caso` | Caso asignado en la extensión al extraer (vacío si no se asignó). |
| `Fecha_Extraccion` | Momento de la extracción. |
| `ID_Extraccion` | Identificador de la corrida de extracción. |
| `Duplicado_Exacto` | Fila idéntica a otra en TODAS sus columnas (extracción repetida). Es False en todo el corpus. NO marca textos repetidos: para eso hay que normalizar Texto_Comentario. |
| `Duplicado_Por_ID` | Mismo ID_Comentario que otra fila de la misma plataforma. En Facebook y TikTok el ID es un hash de autor+texto, así que marca a la misma persona pegando el mismo comentario en otra publicación (nunca dentro de la misma). La clave única es ID_Post_Origen + ID_Comentario. |
| `Parent_Source` | Origen del vínculo con el padre: ID explícito o mención inicial inferida. |
| `Parent_Confidence` | Confianza de ese vínculo. |
| `Texto_Truncado` | El texto parece cortado por la plataforma. |
| `Archivo_Origen` | CSV crudo de origen (en la carpeta crudos/ de su plataforma). |
| `Fila_Origen` | Fila dentro de ese CSV. |
