"""Provision pinned model during build; never send article content to a remote provider."""
import argparse

from huggingface_hub import snapshot_download

from supportflow_ai.domain.knowledge import PROFILE

parser = argparse.ArgumentParser()
parser.add_argument("--cache-dir", required=True)
args = parser.parse_args()
snapshot_download(
    PROFILE.model, revision=PROFILE.model_revision, cache_dir=args.cache_dir,
    allow_patterns=["*.json", "*.safetensors", "*.model", "1_Pooling/*"],
    ignore_patterns=["onnx/*", "openvino/*"],
)
