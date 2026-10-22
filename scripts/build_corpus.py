#!/usr/bin/env python3
"""Build reproducible analysis datasets from Exodoxa scraper exports.

The pipeline uses only Python's standard library. It supports CSV, JSON,
SpreadsheetML 2003 files saved with an .xls extension, and basic OOXML .xlsx
workbooks. Raw files are copied byte-for-byte and are never modified.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import unicodedata
import zipfile
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, parse_qs, urlencode, urlparse, urlunparse
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = ROOT / "data" / "raw"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "processed"

BASE_COLUMNS = [
    "#",
    "Tipo_Elemento",
    "ID_Post_Origen",
    "ID_Comentario",
    "ID_Comentario_Padre",
    "Autor",
    "Usuario_Arroba",
    "Texto_Comentario",
    "Fecha_Comentario",
    "Likes_Comentario",
    "Respuestas_Comentario",
    "Post_Views",
    "Post_Likes",
    "Post_Shares",
    "Post_Comentarios_Total",
    "Post_Fecha",
    "Ventana_Debate",
    "Plataforma",
    "ID_Caso",
    "ID_Extraccion",
    "URL_Origen",
    "Fecha_Extraccion",
]

DERIVED_COLUMNS = [
    "Nivel_Comentario",
    "Fecha_Precision",
    "Texto_Truncado",
    "Segundos_Desde_Post",
    "Duplicado_Exacto",
    "Duplicado_Por_ID",
    "Parent_Source",
    "Parent_Confidence",
    "Archivo_Origen",
    "Fila_Origen",
]

NUMERIC_COLUMNS = {
    "#",
    "Likes_Comentario",
    "Respuestas_Comentario",
    "Post_Views",
    "Post_Likes",
    "Post_Shares",
    "Post_Comentarios_Total",
}

POST_CONTEXT_COLUMNS = [
    "ID_Post_Origen",
    "Post_Views",
    "Post_Likes",
    "Post_Shares",
    "Post_Comentarios_Total",
    "Post_Fecha",
    "Ventana_Debate",
    "Plataforma",
    "ID_Caso",
    "ID_Extraccion",
    "URL_Origen",
    "Fecha_Extraccion",
]

POST_OUTPUT_COLUMNS = [
    "ID_Post_Origen",
    "Plataforma",
    "ID_Caso",
    "Post_Fecha",
    "Post_Views",
    "Post_Likes",
    "Post_Shares",
    "Post_Comentarios_Total",
    "URL_Origen",
]

PUBLICATION_REGISTRY_COLUMNS = [
    "Clave_Publicacion",
    "Estado",
    "Plataforma",
    "ID_Post_Origen",
    "ID_Caso",
    "URL_Origen",
    "URLs_Observadas",
    "URL_Disponible",
    "Primera_Extraccion",
    "Ultima_Extraccion",
    "Numero_Extracciones",
    "Filas",
    "Comentarios",
    "Respuestas",
]

SUPPORTED_EXTENSIONS = {".csv", ".json", ".xls", ".xlsx"}
SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "node_modules",
    "site-packages",
    "venv",
    "__pycache__",
}

SS_NS = "urn:schemas-microsoft-com:office:spreadsheet"
OOXML_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def normalized_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lstrip("\ufeff"))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", "", text.lower())


COLUMN_BY_NORMALIZED = {normalized_name(column): column for column in BASE_COLUMNS}
COLUMN_BY_NORMALIZED["numero"] = "#"
COLUMN_BY_NORMALIZED["n"] = "#"

ALIASES = {
    "tipo": "Tipo_Elemento",
    "elemento": "Tipo_Elemento",
    "idpost": "ID_Post_Origen",
    "postid": "ID_Post_Origen",
    "idcomentariopadre": "ID_Comentario_Padre",
    "parentid": "ID_Comentario_Padre",
    "username": "Usuario_Arroba",
    "usuario": "Usuario_Arroba",
    "texto": "Texto_Comentario",
    "comentario": "Texto_Comentario",
    "fecha": "Fecha_Comentario",
    "tiempo": "Fecha_Comentario",
    "likes": "Likes_Comentario",
    "respuestas": "Respuestas_Comentario",
    "plataform": "Plataforma",
    "platform": "Plataforma",
    "url": "URL_Origen",
}

SUMMARY_FIELDS = {
    "plataforma": "Plataforma",
    "iddelpost": "ID_Post_Origen",
    "idpost": "ID_Post_Origen",
    "visualizaciones": "Post_Views",
    "views": "Post_Views",
    "likes": "Post_Likes",
    "compartidos": "Post_Shares",
    "shares": "Post_Shares",
    "totalcomentarios": "Post_Comentarios_Total",
    "fechadepublicacion": "Post_Fecha",
    "ventanadedebate": "Ventana_Debate",
    "urldeorigen": "URL_Origen",
    "iddeextraccion": "ID_Extraccion",
    "fechadeextraccion": "Fecha_Extraccion",
}

TYPE_VALUES = {
    "comentario": "Comentario",
    "comment": "Comentario",
    "respuesta": "Respuesta",
    "reply": "Respuesta",
    "postprincipal": "Post_Principal",
    "post": "Post_Principal",
}

PLATFORM_VALUES = {
    "facebook": "Facebook",
    "fb": "Facebook",
    "instagram": "Instagram",
    "ig": "Instagram",
    "x": "X",
    "twitter": "X",
    "tiktok": "TikTok",
    "tik tok": "TikTok",
}

TRUNCATION_RE = re.compile(
    r"(?:\bsee\s+more|\bver\s+m[aá]s|\bmostrar\s+m[aá]s)\s*[.\u2026]?\s*$",
    re.IGNORECASE,
)


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return isinstance(value, str) and not value.strip()


def clean_scalar(value: Any) -> Any:
    if is_missing(value):
        return None
    if isinstance(value, str):
        return value.strip()
    return value


def parse_number(value: Any) -> int | float | None:
    value = clean_scalar(value)
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if float(value).is_integer() else float(value)
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if not re.fullmatch(r"[+-]?(?:\d+|\d+\.\d+)", text):
        return None
    number = float(text) if "." in text else int(text)
    return int(number) if isinstance(number, float) and number.is_integer() else number


def parse_iso_datetime(value: Any) -> datetime | None:
    value = clean_scalar(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not re.search(r"T\d{2}:\d{2}", text):
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def normalize_date(value: Any) -> str | None:
    value = clean_scalar(value)
    if value is None:
        return None
    text = str(value).strip()
    parsed = parse_iso_datetime(text)
    if parsed:
        utc_value = parsed.astimezone(timezone.utc)
        rendered = utc_value.isoformat(timespec="milliseconds")
        return rendered.replace("+00:00", "Z")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            date.fromisoformat(text)
            return text
        except ValueError:
            pass
    return text


def date_precision(value: Any) -> str:
    value = clean_scalar(value)
    if value is None:
        return "unknown"
    text = str(value).strip()
    if parse_iso_datetime(text):
        return "exact"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            date.fromisoformat(text)
            return "day"
        except ValueError:
            pass
    return "approximate"


def normalize_platform(value: Any, url: Any = None, source_name: str = "") -> str | None:
    value = clean_scalar(value)
    if value is not None:
        normalized = normalized_name(value)
        for raw, canonical in PLATFORM_VALUES.items():
            if normalized == normalized_name(raw):
                return canonical
        return None

    url_value = clean_scalar(url)
    if url_value:
        host = urlparse(str(url_value)).netloc.lower()
        if "facebook.com" in host or host == "fb.com":
            return "Facebook"
        if "instagram.com" in host:
            return "Instagram"
        if host.endswith("x.com") or "twitter.com" in host:
            return "X"
        if "tiktok.com" in host:
            return "TikTok"

    source_base = Path(source_name).stem.lower()
    source_base = "".join(
        ch for ch in unicodedata.normalize("NFKD", source_base)
        if not unicodedata.combining(ch)
    )
    source_tokens = set(re.findall(r"[a-z0-9]+", source_base))
    filename_platforms = [
        ({"facebook", "fb"}, "Facebook"),
        ({"instagram", "ig"}, "Instagram"),
        ({"twitter", "x"}, "X"),
        ({"tiktok"}, "TikTok"),
    ]
    for tokens, canonical in filename_platforms:
        if source_tokens.intersection(tokens):
            return canonical
    return None


def normalize_type(value: Any) -> str | None:
    value = clean_scalar(value)
    if value is None:
        return None
    return TYPE_VALUES.get(normalized_name(value), str(value))


def canonical_column(raw_name: Any) -> str | None:
    if str(raw_name or "").strip().lstrip("\ufeff") == "#":
        return "#"
    key = normalized_name(raw_name)
    return COLUMN_BY_NORMALIZED.get(key) or ALIASES.get(key)


def decode_text_file(path: Path) -> str:
    payload = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")


def read_csv_file(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    text = decode_text_file(path)
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(
        text.splitlines(),
        delimiter=dialect.delimiter,
        quotechar='"',
        doublequote=True,
    )
    return [dict(row) for row in reader], {}


def read_json_file(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    value = json.loads(decode_text_file(path))
    if isinstance(value, list):
        rows = value
    elif isinstance(value, dict):
        rows = value.get("rows") or value.get("comments") or value.get("data") or []
    else:
        rows = []
    return [row for row in rows if isinstance(row, dict)], {}


def spreadsheetml_row_values(row: ET.Element) -> list[Any]:
    values: list[Any] = []
    for cell in row.findall(f"{{{SS_NS}}}Cell"):
        explicit_index = cell.get(f"{{{SS_NS}}}Index")
        if explicit_index:
            while len(values) < int(explicit_index) - 1:
                values.append(None)
        data = cell.find(f"{{{SS_NS}}}Data")
        values.append("".join(data.itertext()) if data is not None else None)
    return values


def rows_to_dicts(matrix: list[list[Any]]) -> list[dict[str, Any]]:
    if not matrix:
        return []
    headers = [str(value or "").strip().lstrip("\ufeff") for value in matrix[0]]
    rows: list[dict[str, Any]] = []
    for values in matrix[1:]:
        row = {
            header: values[index] if index < len(values) else None
            for index, header in enumerate(headers)
            if header
        }
        if any(not is_missing(value) for value in row.values()):
            rows.append(row)
    return rows


def summary_from_matrix(matrix: list[list[Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for values in matrix[1:]:
        if len(values) < 2:
            continue
        target = SUMMARY_FIELDS.get(normalized_name(values[0]))
        if target and not is_missing(values[1]):
            summary[target] = values[1]
    return summary


def read_spreadsheetml(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root = ET.fromstring(path.read_bytes())
    sheets: list[tuple[str, list[list[Any]]]] = []
    for worksheet in root.findall(f".//{{{SS_NS}}}Worksheet"):
        name = worksheet.get(f"{{{SS_NS}}}Name", "")
        table = worksheet.find(f"{{{SS_NS}}}Table")
        matrix = [] if table is None else [
            spreadsheetml_row_values(row) for row in table.findall(f"{{{SS_NS}}}Row")
        ]
        sheets.append((name, matrix))

    summary: dict[str, Any] = {}
    comments: list[dict[str, Any]] = []
    for name, matrix in sheets:
        normalized = normalized_name(name)
        if "resumen" in normalized:
            summary.update(summary_from_matrix(matrix))
        if "comentario" in normalized:
            comments = rows_to_dicts(matrix)
    if not comments:
        for _, matrix in sheets:
            candidate = rows_to_dicts(matrix)
            if is_structured_rows(candidate):
                comments = candidate
                break
    return comments, summary


def xlsx_col_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference.upper())
    result = 0
    for char in letters.group(0) if letters else "A":
        result = result * 26 + ord(char) - ord("A") + 1
    return result - 1


def read_xlsx_matrix(archive: zipfile.ZipFile, sheet_path: str, shared: list[str]) -> list[list[Any]]:
    root = ET.fromstring(archive.read(sheet_path))
    matrix: list[list[Any]] = []
    for row in root.findall(f".//{{{OOXML_NS}}}sheetData/{{{OOXML_NS}}}row"):
        values: list[Any] = []
        for cell in row.findall(f"{{{OOXML_NS}}}c"):
            index = xlsx_col_index(cell.get("r", "A1"))
            while len(values) <= index:
                values.append(None)
            cell_type = cell.get("t")
            if cell_type == "inlineStr":
                inline = cell.find(f"{{{OOXML_NS}}}is")
                value: Any = "".join(inline.itertext()) if inline is not None else None
            else:
                node = cell.find(f"{{{OOXML_NS}}}v")
                value = node.text if node is not None else None
                if cell_type == "s" and value is not None:
                    value = shared[int(value)]
            values[index] = value
        matrix.append(values)
    return matrix


def read_xlsx(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(item.itertext()) for item in strings.findall(f"{{{OOXML_NS}}}si")]

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        targets = {
            rel.get("Id"): rel.get("Target", "")
            for rel in relationships.findall(f"{{{PKG_REL_NS}}}Relationship")
        }
        sheets: list[tuple[str, list[list[Any]]]] = []
        for sheet in workbook.findall(f".//{{{OOXML_NS}}}sheet"):
            rel_id = sheet.get(f"{{{DOC_REL_NS}}}id")
            target = targets.get(rel_id, "")
            sheet_path = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
            sheet_path = str(Path(sheet_path)).replace("\\", "/")
            sheets.append((sheet.get("name", ""), read_xlsx_matrix(archive, sheet_path, shared)))

    summary: dict[str, Any] = {}
    comments: list[dict[str, Any]] = []
    for name, matrix in sheets:
        normalized = normalized_name(name)
        if "resumen" in normalized:
            summary.update(summary_from_matrix(matrix))
        candidate = rows_to_dicts(matrix)
        if "comentario" in normalized or (not comments and is_structured_rows(candidate)):
            comments = candidate
    return comments, summary


def read_export(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return read_csv_file(path)
    if suffix == ".json":
        return read_json_file(path)
    if suffix == ".xlsx":
        return read_xlsx(path)
    if suffix == ".xls":
        prefix = path.read_bytes()[:32].lstrip()
        if prefix.startswith(b"<?xml") or prefix.startswith(b"<Workbook"):
            return read_spreadsheetml(path)
        raise ValueError("Formato .xls binario no soportado; se esperaba SpreadsheetML/XML")
    raise ValueError(f"Extensión no soportada: {suffix}")


def is_current_schema_rows(rows: list[dict[str, Any]]) -> bool:
    if not rows:
        return False
    raw_columns = set().union(*(row.keys() for row in rows[:10]))
    canonical = {canonical_column(column) for column in raw_columns}
    canonical.discard(None)
    recognized_types = {
        normalize_type(row.get(next(
            (name for name in row if canonical_column(name) == "Tipo_Elemento"),
            "Tipo_Elemento",
        )))
        for row in rows
    }
    has_comment_rows = bool(recognized_types.intersection({"Comentario", "Respuesta"}))
    return (
        "Tipo_Elemento" in canonical
        and len(canonical.intersection(BASE_COLUMNS)) >= 6
        and has_comment_rows
    )


def raw_value(row: dict[str, Any], normalized_key: str) -> Any:
    for key, value in row.items():
        if normalized_name(key) == normalized_key:
            return value
    return None


def is_legacy_comment_rows(rows: list[dict[str, Any]]) -> bool:
    if not rows:
        return False
    raw_columns = {normalized_name(key) for row in rows[:500] for key in row}
    has_legacy_shape = {
        "autor",
        "comentario",
    }.issubset(raw_columns) and bool(raw_columns.intersection({"tiempo", "likes", "respuestas"}))
    return has_legacy_shape and any(not is_missing(raw_value(row, "comentario")) for row in rows)


def is_structured_rows(rows: list[dict[str, Any]]) -> bool:
    return is_current_schema_rows(rows) or is_legacy_comment_rows(rows)


def infer_legacy_platform(rows: list[dict[str, Any]]) -> str | None:
    platforms = unique_non_missing(
        normalize_platform(None, raw_value(row, "url")) for row in rows
    )
    return platforms[0] if len(platforms) == 1 else None


def looks_like_candidate(path: Path) -> bool:
    if "exodoxa" in normalized_name(path.name):
        return True
    try:
        if path.suffix.lower() == ".xlsx":
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if name.startswith("xl/") and name.endswith(".xml"):
                        if b"Tipo_Elemento" in archive.read(name):
                            return True
            return False
        return b"Tipo_Elemento" in path.read_bytes()[:262144]
    except (OSError, zipfile.BadZipFile):
        return False


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_files(root: Path) -> Iterable[Path]:
    def ignore_walk_error(_: OSError) -> None:
        return None

    for current, directory_names, file_names in os.walk(root, onerror=ignore_walk_error):
        directory_names[:] = [
            name for name in directory_names if name.lower() not in SKIP_DIR_NAMES
        ]
        current_path = Path(current)
        # A directory holding _build_report.json is output from a previous run, not a
        # source of exports. Its comments.csv carries Tipo_Elemento, so without this the
        # importer would re-ingest generated rows as if they were a fresh extraction.
        if (current_path / "_build_report.json").exists():
            directory_names[:] = []
            continue
        for file_name in file_names:
            path = current_path / file_name
            if path.suffix.lower() in SUPPORTED_EXTENSIONS and looks_like_candidate(path):
                yield path


def import_raw(import_dirs: list[Path], raw_dir: Path) -> dict[str, Any]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    included: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()
    for source_root in import_dirs:
        source_root = source_root.resolve()
        if not source_root.exists():
            rejected.append({"source": str(source_root), "reason": "directorio inexistente"})
            continue
        for source in discover_files(source_root):
            source = source.resolve()
            if source in seen_paths or raw_dir.resolve() in source.parents:
                continue
            seen_paths.add(source)
            try:
                rows, _ = read_export(source)
                if not is_structured_rows(rows):
                    rejected.append({
                        "source": str(source),
                        "reason": "no contiene el esquema estructurado de comentarios de Exodoxa",
                    })
                    continue
                relative = source.relative_to(source_root)
                destination = raw_dir / normalized_name(source_root.name) / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                source_hash = file_sha256(source)
                if destination.exists() and file_sha256(destination) != source_hash:
                    destination = destination.with_name(
                        f"{destination.stem}__{source_hash[:10]}{destination.suffix}"
                    )
                if not destination.exists():
                    shutil.copy2(source, destination)
                included.append({
                    "source": str(source),
                    "raw_file": destination.relative_to(ROOT).as_posix(),
                    "sha256": source_hash,
                    "bytes": source.stat().st_size,
                })
            except Exception as exc:  # report malformed candidates without stopping the corpus
                rejected.append({"source": str(source), "reason": f"error de lectura: {exc}"})

    manifest = {"included": included, "rejected_candidates": rejected}
    write_json(raw_dir / "_import_manifest.json", manifest)
    return manifest


def unique_non_missing(values: Iterable[Any]) -> list[Any]:
    unique: list[Any] = []
    seen: set[str] = set()
    for value in values:
        if is_missing(value):
            continue
        marker = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if marker not in seen:
            seen.add(marker)
            unique.append(value)
    return unique


def normalize_row(raw: dict[str, Any], source_name: str, row_number: int) -> dict[str, Any]:
    row = {column: None for column in BASE_COLUMNS}
    for raw_name, value in raw.items():
        column = canonical_column(raw_name)
        if column:
            cleaned = clean_scalar(value)
            if not is_missing(cleaned) or is_missing(row[column]):
                row[column] = cleaned
    for column in NUMERIC_COLUMNS:
        row[column] = parse_number(row[column])
    row["Tipo_Elemento"] = normalize_type(row["Tipo_Elemento"])
    row["Fecha_Comentario"] = normalize_date(row["Fecha_Comentario"])
    row["Post_Fecha"] = normalize_date(row["Post_Fecha"])
    row["Fecha_Extraccion"] = normalize_date(row["Fecha_Extraccion"])
    row["Plataforma"] = normalize_platform(row["Plataforma"], row["URL_Origen"], source_name)
    repair_instagram_post_date(row)
    row["Archivo_Origen"] = source_name
    row["Fila_Origen"] = row_number
    return row


def normalize_summary(summary: dict[str, Any], source_name: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in summary.items():
        if key in NUMERIC_COLUMNS:
            result[key] = parse_number(value)
        elif key in {"Post_Fecha", "Fecha_Extraccion"}:
            result[key] = normalize_date(value)
        else:
            result[key] = clean_scalar(value)
    result["Plataforma"] = normalize_platform(
        result.get("Plataforma"), result.get("URL_Origen"), source_name
    )
    return result


def add_derivatives(row: dict[str, Any]) -> None:
    element_type = row.get("Tipo_Elemento")
    parent_id = row.get("ID_Comentario_Padre")
    if element_type == "Respuesta" or not is_missing(parent_id):
        row["Nivel_Comentario"] = 1
    elif element_type == "Comentario":
        row["Nivel_Comentario"] = 0
    else:
        row["Nivel_Comentario"] = None

    row["Fecha_Precision"] = date_precision(row.get("Fecha_Comentario"))
    text = clean_scalar(row.get("Texto_Comentario"))
    row["Texto_Truncado"] = True if text and TRUNCATION_RE.search(str(text)) else None

    comment_date = parse_iso_datetime(row.get("Fecha_Comentario"))
    post_date = parse_iso_datetime(row.get("Post_Fecha"))
    if comment_date and post_date:
        difference = int((comment_date - post_date).total_seconds())
        row["Segundos_Desde_Post"] = difference if difference >= 0 else None
    else:
        row["Segundos_Desde_Post"] = None


IG_SHORTCODE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
IG_EPOCH_MS = 1314220021721
IG_SHORTCODE_RE = re.compile(r"/(?:reels|reel|tv|p)/([A-Za-z0-9_-]{1,11})(?:/|$|\?)")


def instagram_shortcode_datetime(shortcode: Any) -> str | None:
    """Creation time encoded in an Instagram shortcode, as an ISO-8601 UTC string.

    The shortcode is the media id in base64url, and (id >> 23) is milliseconds since
    Instagram's epoch. Mirrors _igShortcodeToIso in content.js.
    """
    if not isinstance(shortcode, str) or not 10 <= len(shortcode) <= 11:
        return None
    media_id = 0
    for char in shortcode:
        digit = IG_SHORTCODE_ALPHABET.find(char)
        if digit < 0:
            return None
        media_id = media_id * 64 + digit
    seconds = ((media_id >> 23) + IG_EPOCH_MS) // 1000
    moment = datetime.fromtimestamp(seconds, tz=timezone.utc)
    if not datetime(2010, 1, 1, tzinfo=timezone.utc) < moment < datetime.now(timezone.utc):
        return None
    return moment.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def repair_instagram_post_date(row: dict[str, Any]) -> None:
    """Replace Instagram's Post_Fecha with the date encoded in the post's shortcode.

    content.js before v1.16 read the first <time> of the comments dialog, which is a
    comment's date, not the post's: verified live 2026-10-15 and against the corpus,
    where 7 of 8 Instagram posts carried a comment's date (one re-export even stamped
    the newest comment's date, a month after publication). The shortcode is in every
    row, so this repairs existing exports without re-extracting.
    """
    if row.get("Plataforma") != "Instagram":
        return
    shortcode = row.get("ID_Post_Origen")
    if is_missing(shortcode) and isinstance(row.get("URL_Origen"), str):
        match = IG_SHORTCODE_RE.search(row["URL_Origen"])
        shortcode = match.group(1) if match else None
    decoded = instagram_shortcode_datetime(shortcode)
    if decoded:
        row["Post_Fecha"] = decoded


def repair_facebook_permalink_post_id(row: dict[str, Any]) -> None:
    """Fix ID_Post_Origen for rows scraped before the content.js permalink fix.

    A Facebook permalink.php URL (facebook.com/permalink.php?story_fbid=...) has no post
    identity in its path, so an older content.js read the literal last path segment and
    stamped every such row with ID_Post_Origen == "permalink.php" -- verified live in one
    real corpus: 3,041 of 6,205 Facebook rows (49%) collapsed onto that one fake id, merging
    unrelated posts into the same publication/dedup/reply-parent-inference bucket. The real
    id was sitting in the URL the whole time as story_fbid (same pfbid... identity already
    used for /posts/{pfbid}/ URLs). This repairs existing raw exports; new scrapes already
    get the right id directly from content.js.
    """
    if row.get("Plataforma") != "Facebook" or row.get("ID_Post_Origen") != "permalink.php":
        return
    url = row.get("URL_Origen")
    if not isinstance(url, str) or not url:
        return
    story_fbid = parse_qs(urlparse(url).query).get("story_fbid", [None])[0]
    if story_fbid:
        row["ID_Post_Origen"] = story_fbid


def _identity(value: Any) -> str:
    value = clean_scalar(value)
    value = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return re.sub(r"[^\w]+", "", value, flags=re.UNICODE)


def infer_parent_links(comments: list[dict[str, Any]]) -> None:
    """Recover high-confidence reply links from explicit leading mentions.

    Some Facebook exports flatten replies into comments and omit the parent ID.
    We only infer a parent when a leading @mention exactly matches a username or
    display name already observed in the same publication context and earlier
    in the export. We never infer a link from adjacency alone.
    """
    mention_re = re.compile(r"^\s*@([^\s,;:!?]+)", re.UNICODE)
    contexts: dict[tuple[Any, Any, Any], list[dict[str, Any]]] = defaultdict(list)

    def context(row: dict[str, Any]) -> tuple[Any, Any, Any]:
        return (row.get("Plataforma"), row.get("ID_Post_Origen"), row.get("URL_Origen"))

    for row in comments:
        row.setdefault("Parent_Source", None)
        row.setdefault("Parent_Confidence", None)
        if not is_missing(row.get("ID_Comentario_Padre")):
            row["Parent_Source"] = "explicit_id"
            row["Parent_Confidence"] = "high"
            contexts[context(row)].append(row)
            continue

        text = str(row.get("Texto_Comentario") or "")
        mention_match = mention_re.match(text)
        candidates = contexts.get(context(row), [])
        parent = None
        confidence = None
        if mention_match and candidates:
            token = _identity(mention_match.group(1))
            username_matches = [candidate for candidate in candidates if token and token == _identity(candidate.get("Usuario_Arroba"))]
            author_matches = [candidate for candidate in candidates if token and token == _identity(candidate.get("Autor"))]
            matches = username_matches or author_matches
            unique_ids = {str(candidate.get("ID_Comentario")) for candidate in matches if not is_missing(candidate.get("ID_Comentario"))}
            if len(unique_ids) == 1:
                wanted = next(iter(unique_ids))
                parent = next(candidate for candidate in matches if str(candidate.get("ID_Comentario")) == wanted)
                confidence = "high" if username_matches else "medium"
        if parent is None and candidates and text:
            # Facebook often exports a reply as: "Nombre del comentario padre ..."
            # without the @ marker. Match only a leading, exact display name and
            # reject ambiguous repeated names rather than guessing.
            prefix_matches = []
            text_folded = unicodedata.normalize("NFKC", text).casefold()
            for candidate in candidates:
                for field in ("Autor", "Usuario_Arroba"):
                    raw_name = clean_scalar(candidate.get(field))
                    if len(str(raw_name or "")) < 4:
                        continue
                    name_folded = unicodedata.normalize("NFKC", str(raw_name)).casefold()
                    if text_folded.startswith(name_folded) and (len(text_folded) == len(name_folded) or not text_folded[len(name_folded)].isalnum()):
                        prefix_matches.append((candidate, len(name_folded)))
                        break
            longest = max((length for _, length in prefix_matches), default=0)
            matches = [candidate for candidate, length in prefix_matches if length == longest]
            unique_ids = {str(candidate.get("ID_Comentario")) for candidate in matches if not is_missing(candidate.get("ID_Comentario"))}
            if len(unique_ids) == 1:
                wanted = next(iter(unique_ids))
                parent = next(candidate for candidate in matches if str(candidate.get("ID_Comentario")) == wanted)
                confidence = "medium"
        if parent:
            row["ID_Comentario_Padre"] = parent.get("ID_Comentario")
            row["Parent_Source"] = "inferred_leading_mention" if mention_match else "inferred_leading_author"
            row["Parent_Confidence"] = confidence
            row["Nivel_Comentario"] = 1
        contexts[context(row)].append(row)


def is_inside(path: Path, parent: Path | None) -> bool:
    if parent is None:
        return False
    try:
        path.resolve().relative_to(parent.resolve())
    except (ValueError, OSError):
        return False
    return True


def load_comments(
    raw_dir: Path,
    exclude_dir: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    comments: list[dict[str, Any]] = []
    unclassified: list[dict[str, Any]] = []
    file_reports: list[dict[str, Any]] = []
    # exclude_dir keeps the build from eating its own output when the output directory
    # sits inside the raw directory: the generated comments.csv carries Tipo_Elemento,
    # so a second run would otherwise re-ingest it as if it were a fresh export.
    paths = sorted(
        path for path in raw_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
        and not path.name.startswith("_")
        and not is_inside(path, exclude_dir)
    )
    for path in paths:
        source_name = path.relative_to(raw_dir).as_posix()
        try:
            raw_rows, raw_summary = read_export(path)
            if not is_structured_rows(raw_rows):
                file_reports.append({"file": source_name, "status": "skipped", "rows": 0})
                continue
            legacy_format = is_legacy_comment_rows(raw_rows) and not is_current_schema_rows(raw_rows)
            rows = [normalize_row(raw, source_name, index) for index, raw in enumerate(raw_rows, 2)]
            summary = normalize_summary(raw_summary, source_name)
            if legacy_format:
                summary["Plataforma"] = infer_legacy_platform(raw_rows)
                for raw, row in zip(raw_rows, rows):
                    row["URL_Origen"] = None
                    row["Tipo_Elemento"] = (
                        "Comentario"
                        if not is_missing(raw_value(raw, "comentario"))
                        else "Contenido_Legacy"
                    )
            post_rows = [row for row in rows if row.get("Tipo_Elemento") == "Post_Principal"]

            context: dict[str, Any] = {}
            for column in POST_CONTEXT_COLUMNS:
                candidates = unique_non_missing([
                    summary.get(column),
                    *(row.get(column) for row in post_rows),
                    *(row.get(column) for row in rows),
                ])
                if len(candidates) == 1:
                    context[column] = candidates[0]

            added = 0
            excluded = 0
            for row in rows:
                if row.get("Tipo_Elemento") == "Post_Principal":
                    continue
                for column, value in context.items():
                    if is_missing(row.get(column)):
                        row[column] = value
                row["Plataforma"] = normalize_platform(
                    row.get("Plataforma"), row.get("URL_Origen"), source_name
                )
                add_derivatives(row)
                repair_facebook_permalink_post_id(row)
                if row.get("Tipo_Elemento") not in {None, "Comentario", "Respuesta"}:
                    unclassified.append(row)
                    excluded += 1
                    continue
                comments.append(row)
                added += 1
            file_reports.append({
                "file": source_name,
                "status": "processed",
                "rows": added,
                "unclassified_rows": excluded,
            })
        except Exception as exc:
            file_reports.append({"file": source_name, "status": "error", "rows": 0, "error": str(exc)})

    infer_parent_links(comments)
    exact_keys = [column for column in BASE_COLUMNS if column != "#"]
    exact_counts = Counter(
        tuple(json.dumps(row.get(column), ensure_ascii=False, sort_keys=True) for column in exact_keys)
        for row in comments
    )
    id_counts = Counter(
        (row.get("Plataforma"), str(row.get("ID_Comentario")))
        for row in comments
        if not is_missing(row.get("ID_Comentario"))
    )
    for row in comments:
        exact_key = tuple(
            json.dumps(row.get(column), ensure_ascii=False, sort_keys=True) for column in exact_keys
        )
        row["Duplicado_Exacto"] = exact_counts[exact_key] > 1
        comment_id = row.get("ID_Comentario")
        row["Duplicado_Por_ID"] = (
            False if is_missing(comment_id)
            else id_counts[(row.get("Plataforma"), str(comment_id))] > 1
        )
    return comments, file_reports, unclassified


def reconcile(values: Iterable[Any]) -> Any:
    candidates = unique_non_missing(values)
    return candidates[0] if len(candidates) == 1 else None


def platform_slug(value: Any) -> str:
    platform = normalize_platform(value)
    return {
        "Facebook": "facebook",
        "Instagram": "instagram",
        "TikTok": "tiktok",
        "X": "x",
    }.get(platform, "desconocida")


def normalize_url_for_comparison(value: Any) -> str | None:
    value = clean_scalar(value)
    if value is None:
        return None
    text = str(value).strip()
    if not re.match(r"^https?://", text, re.IGNORECASE):
        text = "https://" + text
    try:
        parsed = urlparse(text)
    except ValueError:
        return None
    host = parsed.netloc.lower().split("@")[-1]
    if host.startswith("www."):
        host = host[4:]
    if host.startswith("m."):
        host = host[2:]
    if not host:
        return None
    path = re.sub(r"/{2,}", "/", parsed.path).rstrip("/") or "/"
    ignored_query_keys = {
        "fbclid",
        "igsh",
        "igshid",
        "mibextid",
        "ref",
        "ref_src",
        "s",
        "t",
        "utm_campaign",
        "utm_content",
        "utm_medium",
        "utm_source",
        "utm_term",
    }
    query = urlencode(sorted(
        (key, item)
        for key, item in parse_qsl(parsed.query, keep_blank_values=False)
        if key.lower() not in ignored_query_keys
    ))
    return urlunparse(("https", host, path, "", query, ""))


def identity_from_url(value: Any, platform: Any = None) -> str | None:
    normalized_url = normalize_url_for_comparison(value)
    if normalized_url is None:
        return None
    parsed = urlparse(normalized_url)
    host = parsed.netloc.lower()
    path_parts = [part for part in parsed.path.split("/") if part]
    detected = normalize_platform(platform, normalized_url)

    if detected == "Instagram":
        for marker in ("p", "reel", "tv"):
            if marker in path_parts:
                index = path_parts.index(marker)
                if index + 1 < len(path_parts):
                    return f"instagram:{path_parts[index + 1]}"

    if detected == "X" and "status" in path_parts:
        index = path_parts.index("status")
        if index + 1 < len(path_parts) and re.fullmatch(r"\d+", path_parts[index + 1]):
            return f"x:{path_parts[index + 1]}"

    if detected == "TikTok" and "video" in path_parts:
        index = path_parts.index("video")
        if index + 1 < len(path_parts) and re.fullmatch(r"\d+", path_parts[index + 1]):
            return f"tiktok:{path_parts[index + 1]}"

    if detected == "Facebook":
        query = parse_qs(parsed.query)
        for key in ("story_fbid", "fbid", "v"):
            candidate = clean_scalar((query.get(key) or [None])[0])
            if candidate:
                return f"facebook:{candidate}"
        for marker in ("posts", "videos", "reel"):
            if marker in path_parts:
                index = path_parts.index(marker)
                if index + 1 < len(path_parts):
                    return f"facebook:{path_parts[index + 1]}"

    return f"url:{normalized_url}"


def publication_key(row: dict[str, Any]) -> str | None:
    platform = row.get("Plataforma")
    post_id = clean_scalar(row.get("ID_Post_Origen"))
    if post_id is not None:
        return f"{platform_slug(platform)}:{post_id}"
    return identity_from_url(row.get("URL_Origen"), platform)


def collect_post_groups(
    comments: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in comments:
        has_any_post_metadata = any(
            not is_missing(row.get(column))
            for column in (
                "ID_Post_Origen",
                "Post_Fecha",
                "Post_Views",
                "Post_Likes",
                "Post_Shares",
                "Post_Comentarios_Total",
                "URL_Origen",
            )
        )
        if not has_any_post_metadata:
            continue
        key = publication_key(row)
        if key is None:
            source_marker = str(row.get("Archivo_Origen") or "sin-origen")
            digest = hashlib.sha256(source_marker.encode("utf-8")).hexdigest()[:12]
            key = f"{platform_slug(row.get('Plataforma'))}:sin-id:{digest}"
        groups[key].append(row)
    return dict(groups)


def build_posts(comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups = collect_post_groups(comments)
    return [
        {column: reconcile(row.get(column) for row in rows) for column in POST_OUTPUT_COLUMNS}
        for _, rows in sorted(groups.items())
    ]


def build_publication_registry(comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    registry: list[dict[str, Any]] = []
    for key, rows in sorted(collect_post_groups(comments).items()):
        urls = unique_non_missing(row.get("URL_Origen") for row in rows)
        extraction_dates = sorted(
            value
            for value in unique_non_missing(row.get("Fecha_Extraccion") for row in rows)
            if parse_iso_datetime(value)
        )
        extraction_ids = unique_non_missing(row.get("ID_Extraccion") for row in rows)
        registry.append({
            "Clave_Publicacion": key,
            "Estado": "Scrapeado",
            "Plataforma": reconcile(row.get("Plataforma") for row in rows),
            "ID_Post_Origen": reconcile(row.get("ID_Post_Origen") for row in rows),
            "ID_Caso": reconcile(row.get("ID_Caso") for row in rows),
            "URL_Origen": urls[0] if len(urls) == 1 else None,
            "URLs_Observadas": " | ".join(str(url) for url in urls) if urls else None,
            "URL_Disponible": bool(urls),
            "Primera_Extraccion": extraction_dates[0] if extraction_dates else None,
            "Ultima_Extraccion": extraction_dates[-1] if extraction_dates else None,
            "Numero_Extracciones": len(extraction_ids) if extraction_ids else None,
            "Filas": len(rows),
            "Comentarios": sum(row.get("Nivel_Comentario") == 0 for row in rows),
            "Respuestas": sum(row.get("Nivel_Comentario") == 1 for row in rows),
        })
    return registry


def build_edges(comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source": row.get("ID_Comentario_Padre"),
            "target": row.get("ID_Comentario"),
            "Plataforma": row.get("Plataforma"),
            "ID_Extraccion": row.get("ID_Extraccion"),
            "Archivo_Origen": row.get("Archivo_Origen"),
            "Parent_Source": row.get("Parent_Source"),
            "Parent_Confidence": row.get("Parent_Confidence"),
        }
        for row in comments
        if not is_missing(row.get("ID_Comentario_Padre"))
        and not is_missing(row.get("ID_Comentario"))
    ]


def build_timeline(comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    timeline = []
    for row in comments:
        if row.get("Fecha_Precision") not in {"exact", "day"}:
            continue
        timeline.append({
            "Fecha": row.get("Fecha_Comentario"),
            "Fecha_Precision": row.get("Fecha_Precision"),
            "Plataforma": row.get("Plataforma"),
            "Tipo_Elemento": row.get("Tipo_Elemento"),
            "ID_Comentario": row.get("ID_Comentario"),
            "ID_Post_Origen": row.get("ID_Post_Origen"),
            "Likes_Comentario": row.get("Likes_Comentario"),
            "Segundos_Desde_Post": row.get("Segundos_Desde_Post"),
            "Archivo_Origen": row.get("Archivo_Origen"),
        })
    return sorted(timeline, key=lambda row: str(row.get("Fecha") or ""))


def percent(numerator: int, denominator: int) -> float:
    return round((100.0 * numerator / denominator), 2) if denominator else 0.0


def has_complete_post_metadata(row: dict[str, Any]) -> bool:
    required = [
        "ID_Post_Origen",
        "Post_Views",
        "Post_Likes",
        "Post_Shares",
        "Post_Comentarios_Total",
        "Post_Fecha",
    ]
    return all(not is_missing(row.get(column)) for column in required)


def platform_groups(comments: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in comments:
        groups[str(row.get("Plataforma") or "Desconocida")].append(row)
    return dict(sorted(groups.items()))


def build_platform_summary(
    comments: list[dict[str, Any]], posts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    post_counts = Counter(str(post.get("Plataforma") or "Desconocida") for post in posts)
    output = []
    for platform, rows in platform_groups(comments).items():
        count = len(rows)
        output.append({
            "Plataforma": platform,
            "filas": count,
            "comentarios": sum(row.get("Nivel_Comentario") == 0 for row in rows),
            "respuestas": sum(row.get("Nivel_Comentario") == 1 for row in rows),
            "posts": post_counts[platform],
            "likes_acumulados": sum(row.get("Likes_Comentario") or 0 for row in rows),
            "porcentaje_con_fecha": percent(sum(not is_missing(row.get("Fecha_Comentario")) for row in rows), count),
            "porcentaje_con_id_comentario": percent(sum(not is_missing(row.get("ID_Comentario")) for row in rows), count),
            "porcentaje_con_id_padre": percent(sum(not is_missing(row.get("ID_Comentario_Padre")) for row in rows), count),
            "porcentaje_con_texto": percent(sum(not is_missing(row.get("Texto_Comentario")) for row in rows), count),
            "porcentaje_con_metadata_post": percent(sum(has_complete_post_metadata(row) for row in rows), count),
        })
    return output


def build_quality(comments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for platform, rows in platform_groups(comments).items():
        replies = [row for row in rows if row.get("Nivel_Comentario") == 1]
        output.append({
            "Plataforma": platform,
            "filas_totales": len(rows),
            "ids_faltantes": sum(is_missing(row.get("ID_Comentario")) for row in rows),
            "parent_ids_faltantes": sum(is_missing(row.get("ID_Comentario_Padre")) for row in replies),
            "fechas_faltantes": sum(is_missing(row.get("Fecha_Comentario")) for row in rows),
            "textos_vacios": sum(is_missing(row.get("Texto_Comentario")) for row in rows),
            "metadata_post_faltante": sum(not has_complete_post_metadata(row) for row in rows),
            "posibles_textos_truncados": sum(row.get("Texto_Truncado") is True for row in rows),
            "duplicados_exactos": sum(row.get("Duplicado_Exacto") is True for row in rows),
            "duplicados_por_id": sum(row.get("Duplicado_Por_ID") is True for row in rows),
        })
    return output


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def write_dataset(output_dir: Path, name: str, rows: list[dict[str, Any]], columns: list[str]) -> None:
    write_csv(output_dir / f"{name}.csv", rows, columns)
    write_json(output_dir / f"{name}.json", rows)


def write_global_script(path: Path, variable: str, value: Any) -> None:
    """Emit the dataset as a plain <script> assignment.

    The dashboard must work when index.html is opened by double-clicking it,
    and Chrome blocks fetch() over file://. A script tag is not subject to that
    restriction, so the page reads the global and only falls back to fetch when
    the global is absent. JSON is still the canonical artifact; this is a second
    encoding of the same rows, never a second source of truth.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    # A literal "</script>" inside string data would close the tag early.
    payload = payload.replace("</", "<\\/")
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("// GENERADO por analysis/build_corpus.py - no editar a mano.\n")
        handle.write(f"window.{variable} = {payload};\n")


def build(raw_dir: Path, output_dir: Path) -> dict[str, Any]:
    comments, file_reports, unclassified = load_comments(raw_dir, exclude_dir=output_dir)
    posts = build_posts(comments)
    registry = build_publication_registry(comments)
    edges = build_edges(comments)
    timeline = build_timeline(comments)
    summary = build_platform_summary(comments, posts)
    quality = build_quality(comments)

    write_dataset(output_dir, "comments", comments, BASE_COLUMNS + DERIVED_COLUMNS)
    write_dataset(
        output_dir,
        "unclassified_rows",
        unclassified,
        BASE_COLUMNS + DERIVED_COLUMNS,
    )
    write_dataset(output_dir, "posts", posts, POST_OUTPUT_COLUMNS)
    write_dataset(
        output_dir,
        "publication_registry",
        registry,
        PUBLICATION_REGISTRY_COLUMNS,
    )
    write_global_script(
        output_dir / "publication_registry.js", "EXODOXA_REGISTRY", registry
    )
    write_dataset(
        output_dir,
        "reply_edges",
        edges,
        ["source", "target", "Plataforma", "ID_Extraccion", "Archivo_Origen", "Parent_Source", "Parent_Confidence"],
    )
    write_dataset(
        output_dir,
        "timeline",
        timeline,
        [
            "Fecha",
            "Fecha_Precision",
            "Plataforma",
            "Tipo_Elemento",
            "ID_Comentario",
            "ID_Post_Origen",
            "Likes_Comentario",
            "Segundos_Desde_Post",
            "Archivo_Origen",
        ],
    )
    summary_columns = list(summary[0].keys()) if summary else ["Plataforma"]
    quality_columns = list(quality[0].keys()) if quality else ["Plataforma"]
    write_dataset(output_dir, "platform_summary", summary, summary_columns)
    write_csv(output_dir / "data_quality.csv", quality, quality_columns)
    write_json(output_dir / "data_quality.json", quality)

    report = {
        "raw_files": file_reports,
        "rows": len(comments),
        "posts": len(posts),
        "registered_publications": len(registry),
        "publications_with_url": sum(row["URL_Disponible"] for row in registry),
        "reply_edges": len(edges),
        "timeline_rows": len(timeline),
        "unclassified_rows": len(unclassified),
        "platforms": {row["Plataforma"]: row["filas"] for row in summary},
        "errors": [row for row in file_reports if row["status"] == "error"],
    }
    write_json(output_dir / "_build_report.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--import-dir",
        action="append",
        type=Path,
        default=[],
        help="Directory to scan for structured Exodoxa exports; may be repeated.",
    )
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.import_dir:
        manifest = import_raw(args.import_dir, args.raw_dir)
        print(f"Imported {len(manifest['included'])} structured exports")
        print(f"Rejected {len(manifest['rejected_candidates'])} non-structured candidates")
    report = build(args.raw_dir, args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
