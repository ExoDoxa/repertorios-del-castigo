"""Transcribe el audio de videos de publicaciones con faster-whisper.

    python scripts/transcribir_videos.py VIDEO.mp4 [VIDEO2.mp4 ...] [--modelo small] [--salida carpeta]

Escribe un .txt por video con la transcripción en español. Configuración usada en el estudio:
modelo "small", CPU con cuantización int8, idioma forzado a español y filtro de actividad de voz
(vad_filter). Un video sin voz (solo música) produce un .txt vacío: su contenido se toma entonces
del texto en pantalla.

Los videos NO forman parte de este repositorio. En el estudio se obtuvieron con yt-dlp desde la URL
pública de cada publicación (o desde la propia página cuando yt-dlp falló).

Requiere: pip install faster-whisper  (descarga el modelo la primera vez).
"""
import argparse
from pathlib import Path

from faster_whisper import WhisperModel


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("videos", nargs="+", type=Path)
    ap.add_argument("--modelo", default="small")
    ap.add_argument("--salida", type=Path, default=None, help="Carpeta de salida (por defecto, junto a cada video).")
    args = ap.parse_args()

    modelo = WhisperModel(args.modelo, device="cpu", compute_type="int8")
    for video in args.videos:
        segmentos, info = modelo.transcribe(str(video), language="es", vad_filter=True)
        texto = " ".join(s.text.strip() for s in segmentos)
        destino = (args.salida or video.parent) / f"{video.stem}.txt"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(texto, encoding="utf-8")
        print(f"{video.name} ({info.duration:.0f} s): {len(texto)} caracteres -> {destino}")


if __name__ == "__main__":
    main()
