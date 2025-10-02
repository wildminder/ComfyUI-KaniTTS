import os
import sys
import logging
import folder_paths
from .modules.model_info import AVAILABLE_KANI_MODELS, MODEL_CONFIGS

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter(f"[ComfyUI-KaniTTS] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

KANI_SUBDIR_NAME = "KaniTTS"

tts_path = os.path.join(folder_paths.models_dir, "tts")
os.makedirs(tts_path, exist_ok=True)

if "tts" not in folder_paths.folder_names_and_paths:
    folder_paths.folder_names_and_paths["tts"] = ([tts_path], folder_paths.supported_pt_extensions)
else:
    if tts_path not in folder_paths.folder_names_and_paths["tts"][0]:
        folder_paths.folder_names_and_paths["tts"][0].append(tts_path)

for model_name, config in MODEL_CONFIGS.items():
    AVAILABLE_KANI_MODELS[model_name] = {
        "type": "official",
        **config
    }

kani_search_paths = []
for tts_folder in folder_paths.get_folder_paths("tts"):
    potential_path = os.path.join(tts_folder, KANI_SUBDIR_NAME)
    if os.path.isdir(potential_path) and potential_path not in kani_search_paths:
        kani_search_paths.append(potential_path)

for search_path in kani_search_paths:
    if not os.path.isdir(search_path):
        continue
    for item in os.listdir(search_path):
        item_path = os.path.join(search_path, item)
        if os.path.isdir(item_path) and item not in AVAILABLE_KANI_MODELS:
            config_exists = os.path.exists(os.path.join(item_path, "config.json"))
            weights_exist = any(f.endswith(('.bin', '.safetensors')) for f in os.listdir(item_path))

            if config_exists and weights_exist:
                AVAILABLE_KANI_MODELS[item] = {
                    "type": "local",
                    "path": item_path
                }

# logger.info(f"Available KaniTTS models: {sorted(list(AVAILABLE_KANI_MODELS.keys()))}")

from .kani_tts_nodes import KaniTTSNode

NODE_CLASS_MAPPINGS = {
    "KaniTTS": KaniTTSNode,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "KaniTTS": "Kani TTS",
}

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']