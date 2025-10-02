import os
import torch
import logging
from huggingface_hub import snapshot_download
import folder_paths

logger = logging.getLogger(__name__)

try:
    import nemo.collections.tts.modules.audio_codec_modules as audio_codec_modules

    #  prevent 'wavlm-base-plus'
    class _DummySLMDiscriminator(torch.nn.Module):
        def __init__(self, *args, **kwargs):
            super().__init__()

        def forward(self, *args, **kwargs):
            return None

    audio_codec_modules.SLMDiscriminator = _DummySLMDiscriminator
except Exception as e:
    logger.warning(f"Could not monkey-patch NeMo's. Error: {e}")

from nemo.collections.tts.models import AudioCodecModel
from ..src.kanitts import Config, TTSFactory
from .model_info import AVAILABLE_KANI_MODELS

LOADED_MODELS_CACHE = {}

def get_nemo_codec_path(repo_id="nvidia/nemo-nano-codec-22khz-0.6kbps-12.5fps"):
    """
    Finds or downloads the NeMo codec .nemo file to a clean, predictable path
    within ComfyUI's model directories and returns the full file path.
    """
    model_name_only = repo_id.split('/')[-1]
    
    filename_on_hub = f"{model_name_only}.nemo"
    
    codec_subdir = os.path.join("nemo-codecs", model_name_only)
    
    try:
        found_path = folder_paths.get_full_path("tts", os.path.join(codec_subdir, filename_on_hub))
        if found_path and os.path.exists(found_path):
            return found_path
    except Exception:
        pass

    primary_tts_path = folder_paths.get_folder_paths("tts")[0]
    download_dir = os.path.join(primary_tts_path, codec_subdir)
    
    logger.info(f"NeMo codec not found. Downloading '{filename_on_hub}' to '{download_dir}'...")
    
    snapshot_download(
        repo_id=repo_id,
        local_dir=download_dir,
        allow_patterns=[filename_on_hub],
        local_dir_use_symlinks=False,
    )
    
    final_file_path = os.path.join(download_dir, filename_on_hub)
    if not os.path.exists(final_file_path):
        raise FileNotFoundError(f"Downloaded NeMo codec but failed to find '{filename_on_hub}' in '{download_dir}'")
        
    return final_file_path


class KaniTTSModelHandler(torch.nn.Module):
    """
    A lightweight handler for a KaniTTS model. Acts as a container for
    ComfyUI's ModelPatcher to manage.
    """
    def __init__(self, model_name: str, dtype: str):
        super().__init__()
        self.model_name = model_name
        self.dtype = dtype
        self.model = None
        self.size = int(2.0 * (1024**3))

class KaniTTSLoader:
    @staticmethod
    def load_model(model_name: str, device: torch.device, dtype_str: str):
        """
        Loads both the KaniTTS transformer and its required NeMo codec model.
        """
        cache_key = f"{model_name}_{device.type}_{dtype_str}"
        if cache_key in LOADED_MODELS_CACHE:
            logger.info(f"Using cached KaniTTS system instance: {model_name}")
            return LOADED_MODELS_CACHE[cache_key]

        logger.info("Locating and loading NeMo audio codec...")
        nemo_file_path = get_nemo_codec_path()
        
        codec_model = AudioCodecModel.restore_from(restore_path=nemo_file_path).eval()
        codec_model.to(device)
        logger.info(f"NeMo audio codec loaded and moved to {device}.")

        model_info = AVAILABLE_KANI_MODELS.get(model_name)
        if not model_info:
            raise ValueError(f"Model '{model_name}' not found.")

        kani_model_subdir = os.path.join("KaniTTS", model_name)
        model_path = None
        
        try:
             model_path = folder_paths.get_full_path("tts", kani_model_subdir)
             if not model_path or not os.path.isdir(model_path):
                 raise FileNotFoundError
        except (FileNotFoundError, TypeError):
             if model_info["type"] == "official":
                 primary_tts_path = folder_paths.get_folder_paths("tts")[0]
                 model_path = os.path.join(primary_tts_path, kani_model_subdir)
                 logger.info(f"Downloading official KaniTTS model '{model_name}' to '{model_path}'...")
                 snapshot_download(
                     repo_id=model_info["repo_id"], local_dir=model_path,
                     local_dir_use_symlinks=False, ignore_patterns=["*.flac", "*.jpg"],
                 )
             else:
                 raise RuntimeError(f"Could not find local model directory for '{model_name}'")

        if not os.path.isdir(model_path):
            raise RuntimeError(f"Could not determine a valid path for model '{model_name}'")
        logger.info(f"Using KaniTTS model from: {model_path}")

        logger.info(f"Instantiating KaniTTS transformer on device '{device}' with precision '{dtype_str}'...")
        
        config = Config.default()
        config.model.model_name = model_path
        config.model.torch_dtype = dtype_str
        config.model.device_map = "auto" if device.type == "cuda" else None
        config.audio.device = str(device)
        
        model_instance, _ = TTSFactory.create_system(config, codec_model=codec_model)
        
        LOADED_MODELS_CACHE[cache_key] = model_instance
        return model_instance