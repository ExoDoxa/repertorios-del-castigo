# Datos (no incluidos)

Esta carpeta está vacía a propósito: los datos contienen información personal y no se publican.
Ver la sección "Datos" del README principal.

Para ejecutar los scripts, la estructura esperada es:

```
datos/bases_armonizadas/
├── Facebook_Instagram/crudos/*.csv    exportaciones de la extensión (Facebook e Instagram)
├── TikTok/crudos/*.csv                exportaciones de la extensión (TikTok)
└── registro_publicaciones_crudo/      lectura de las páginas (solo para generar_registro.py)
    ├── captions_fb.json
    ├── captions_ig.json
    ├── captions_tt.json
    └── transcripciones_manuales_2026-10-22.json
```

`generar_bases.py` escribe ahí las tres bases (`.xlsx`) y los `inventario_publicaciones.csv`;
`generar_registro.py` escribe `registro_publicaciones_2026-10-22.xlsx` y `.csv`.
