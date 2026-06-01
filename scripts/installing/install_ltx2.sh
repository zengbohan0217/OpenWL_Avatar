#!/bin/bash
set -e

pip install torch==2.7.1 torchvision==0.22.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu126
pip install transformers==4.57.1

git clone https://github.com/Lightricks/LTX-2.git
cd LTX-2
pip install -e packages/ltx-core -e packages/ltx-pipelines

pip install diffusers
pip install imageio
