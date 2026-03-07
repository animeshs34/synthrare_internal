#!/bin/bash
set -e
apt-get update && apt-get upgrade -y
apt-get install -y python3-pip python3-venv git
python3 -m venv /opt/synthrare-ml
source /opt/synthrare-ml/bin/activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
pip install transformers datasets accelerate peft bitsandbytes sdv ctgan huggingface_hub boto3 pandas scikit-learn scipy
echo "GPU Droplet ready"
echo "WARNING: DESTROY THIS DROPLET when training is complete to stop billing"
