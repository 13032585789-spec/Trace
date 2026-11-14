#!/usr/bin/env bash
# Round 2 (fixtures): train on the images users actually send (F1_original = Junction PNGs) + F1_scaled copies,
# starting from the round-1 weights. Then evaluate both models on F1_original test images.
# Usage on a fresh Verda A100:  bash setup.sh && bash run_round2.sh      (~1.5 h; log: train_cubi_r2.log)
set -e; cd "$(dirname "$0")"; source .venv/bin/activate
IMGS=F1_original,F1_scaled YOLO_DIR=data/yolo_r2 YAML=cubi_r2.yaml python3 cubicasa_to_yolo.py
# baseline: round-1 model, evaluated on F1_original (what Junction / users send)
IMGSZ=1280 OUT_SFX=_r1_on_original python3 predict_counts.py ../models/cubicasa_yolo11m_1280.pt | tee pred_r1_on_original.log
MODEL=../models/cubicasa_yolo11m_1280.pt DATA=data/cubi_r2.yaml NAME=cubi_r2 IMGSZ=1536 EPOCHS=30 BATCH=8 \
  EXTRA="flipud=0.5 lr0=0.003 warmup_epochs=1" bash train.sh
while pgrep -f "yolo detect train" > /dev/null; do sleep 60; done
RUN=cubi_r2 IMGSZ=1536 OUT_SFX=_r2 python3 predict_counts.py | tee pred_r2.log
ls -lh det_cache_r1_on_original.zip det_cache_r2.zip
