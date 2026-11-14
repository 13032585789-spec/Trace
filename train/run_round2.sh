#!/usr/bin/env bash
# Round 2 for doors/windows. On a fresh Verda A100 (80 GB):
#   git clone https://github.com/13032585789-spec/Trace.git trace && cd trace/train && bash setup.sh
#   tmux new -s r2      then      bash run_round2.sh          (~2 h; progress: tail -f r2.log)
# Steps: build labels (std + runs variants, F1_original + F1_scaled) -> fetch public RT-DETR weights ->
#        train r2std and r2runs in parallel from the round-1 weights -> evaluate everything on F1_original.
set -e; cd "$(dirname "$0")"; source .venv/bin/activate
exec > >(tee -a r2.log) 2>&1
echo "== $(date) build labels"
python3 r2_build.py --root data
echo "== $(date) RT-DETR public weights (optional; skipped if the download fails)"
[ -f ../models/rtdetr_l_cubi.pt ] || wget -q -O ../models/rtdetr_l_cubi.pt \
  "https://github.com/OldDeLorean/rtdetr-floorplan-detector/raw/main/weights/rtdetr_l_autoresearch_60ep.pt" \
  || { echo "RT-DETR download failed - continuing without it"; rm -f ../models/rtdetr_l_cubi.pt; }
[ ! -f ../models/rtdetr_l_cubi.pt ] || [ $(stat -c%s ../models/rtdetr_l_cubi.pt) -gt 1000000 ] || { echo "RT-DETR file is not a model (LFS pointer?) - skipping"; rm -f ../models/rtdetr_l_cubi.pt; }
ls -lh ../models/
echo "== $(date) smoke test of the evaluation on 24 plans (catches script errors before the long training)"
SMOKE=1 python3 r2_eval.py
echo "== $(date) train r2std and r2runs in parallel (20 epochs, 1536 px, from round-1 weights)"
COMMON="flipud=0.5 lr0=0.003 warmup_epochs=1 workers=6 patience=8"
MODEL=../models/cubicasa_yolo11m_1280.pt DATA=data/r2std.yaml  NAME=r2std  IMGSZ=1536 EPOCHS=20 BATCH=8 EXTRA="$COMMON" bash train.sh
sleep 90
MODEL=../models/cubicasa_yolo11m_1280.pt DATA=data/r2runs.yaml NAME=r2runs IMGSZ=1536 EPOCHS=20 BATCH=8 EXTRA="$COMMON" bash train.sh
sleep 120; nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv
while pgrep -f "yolo detect train" > /dev/null; do sleep 120; echo "$(date +%H:%M) r2std: $(grep -o '[0-9]*/20' train_r2std.log | tail -1)  r2runs: $(grep -o '[0-9]*/20' train_r2runs.log | tail -1)"; done
echo "== $(date) evaluate on F1_original (the images users send)"
python3 r2_eval.py
ls -lh r2_report.txt r2_dets.zip
find ~ -path "*r2std*" -name best.pt -o -path "*r2runs*" -name best.pt | grep -v .venv
echo "== $(date) done"
