#!/usr/bin/env bash
# Run on the Verda GPU instance (Ubuntu), from trace/train:   bash setup.sh
set -e
cd "$(dirname "$0")"
python3 -m pip install -q --upgrade pip
python3 -m pip install -q ultralytics
mkdir -p data
if [ ! -f data/cubicasa5k.zip ]; then
  echo "downloading CubiCasa5k (5.5 GB) from Zenodo ..."
  wget -q --show-progress -O data/cubicasa5k.zip "https://zenodo.org/records/2613548/files/cubicasa5k.zip?download=1"
fi
echo "0ce0b203d1e3c125b51087b219bd23b9  data/cubicasa5k.zip" | md5sum -c -
[ -d data/cubicasa5k ] || unzip -q data/cubicasa5k.zip -d data/
python3 cubicasa_to_yolo.py --root data --inspect      # prints annotation classes + image/SVG sizes
python3 cubicasa_to_yolo.py --root data                # writes data/yolo + data/split.json
nvidia-smi --query-gpu=name,memory.total --format=csv
echo "SETUP DONE. Next: bash train.sh"
