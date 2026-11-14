#!/usr/bin/env bash
# Install everything the clipper needs: binaries, models, and the optional local LLM.
set -euo pipefail

MODE="both"
SKIP_MODEL=0
CHECK_ONLY=0
OLLAMA_MODEL="${GTA6_CLIPPER_OLLAMA_MODEL:-qwen3.5:27b}"

while [ $# -gt 0 ]; do
  case "$1" in
    --mode) MODE="$2"; shift 2 ;;
    --skip-model) SKIP_MODEL=1; shift ;;
    --check) CHECK_ONLY=1; shift ;;
    --ollama-model) OLLAMA_MODEL="$2"; shift 2 ;;
    -h|--help)
      echo "usage: setup.sh [--mode claude|ollama|both] [--skip-model] [--check] [--ollama-model NAME]"
      exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

CACHE="${GTA6_CLIPPER_CACHE:-$HOME/.cache/gta6-clipper}"
MODEL_DIR="$CACHE/models"
WHISPER_MODEL="$MODEL_DIR/ggml-large-v3-turbo.bin"
FACECAM_MODEL="$MODEL_DIR/face_detection_yunet_2023mar.onnx"

WHISPER_URL="https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin"
FACECAM_URL="https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"

say() { printf '[setup] %s\n' "$*"; }

have() { command -v "$1" >/dev/null 2>&1; }

check_all() {
  local missing=0
  for binary in ffmpeg ffprobe yt-dlp; do
    if have "$binary"; then say "ok   $binary"; else say "MISS $binary"; missing=1; fi
  done
  if have whisper-cli || have main || have whisper-cpp; then say "ok   whisper.cpp"; else say "MISS whisper.cpp"; missing=1; fi
  if [ -f "$WHISPER_MODEL" ]; then say "ok   whisper model"; else say "MISS whisper model"; missing=1; fi
  if [ -f "$FACECAM_MODEL" ]; then say "ok   facecam model"; else say "MISS facecam model"; missing=1; fi
  return $missing
}

if [ "$CHECK_ONLY" -eq 1 ]; then
  if check_all; then
    echo "SETUP OK"
    exit 0
  fi
  exit 1
fi

if ! have brew; then
  say "Homebrew is required: https://brew.sh"
  exit 1
fi

for formula in ffmpeg yt-dlp whisper-cpp; do
  if brew list --formula 2>/dev/null | grep -qx "$formula"; then
    say "have $formula"
  else
    say "installing $formula"
    brew install "$formula"
  fi
done

mkdir -p "$MODEL_DIR"

if [ "$SKIP_MODEL" -eq 0 ]; then
  if [ ! -f "$WHISPER_MODEL" ]; then
    say "downloading whisper model (about 1.6 GB)"
    curl -L --fail --progress-bar -o "$WHISPER_MODEL" "$WHISPER_URL"
  else
    say "have whisper model"
  fi
  if [ ! -f "$FACECAM_MODEL" ]; then
    say "downloading facecam model"
    curl -L --fail --progress-bar -o "$FACECAM_MODEL" "$FACECAM_URL"
  else
    say "have facecam model"
  fi
fi

if [ "$MODE" = "ollama" ] || [ "$MODE" = "both" ]; then
  if ! have ollama; then
    say "installing ollama"
    brew install ollama
  else
    say "have ollama"
  fi
  if ! ollama list >/dev/null 2>&1; then
    say "starting ollama"
    (nohup ollama serve >"$CACHE/ollama.log" 2>&1 &) || true
    sleep 3
  fi
  if ollama list 2>/dev/null | grep -q "^${OLLAMA_MODEL%%:*}"; then
    say "have ollama model $OLLAMA_MODEL"
  else
    say "pulling $OLLAMA_MODEL (this is a large download)"
    ollama pull "$OLLAMA_MODEL"
  fi
fi

say "done. run: gta6-clipper doctor"
