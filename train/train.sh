#!/usr/bin/env bash
# Run on the Verda GPU instance:  bash train.sh     (keeps running if you disconnect; log in train.log)
cd "$(dirname "$0")"
source .venv/bin/activate
MODEL=${MODEL:-yolo11m.pt}; EPOCHS=${EPOCHS:-60}; IMGSZ=${IMGSZ:-1280}; BATCH=${BATCH:-8}; NAME=${NAME:-cubi}
nohup yolo detect train data=data/cubi.yaml model=$MODEL imgsz=$IMGSZ epochs=$EPOCHS batch=$BATCH \
      project=runs name=$NAME exist_ok=True close_mosaic=10 patience=20 > train_$NAME.log 2>&1 &
echo "training started in the background. Watch it with:  tail -f train_$NAME.log   (Ctrl+C stops watching, not training)"
