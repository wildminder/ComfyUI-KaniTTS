import torch
import gc
import logging
import comfy.model_patcher
import comfy.model_management as model_management

from .loader import KaniTTSLoader, LOADED_MODELS_CACHE

logger = logging.getLogger(__name__)

class KaniTTSPatcher(comfy.model_patcher.ModelPatcher):
    """
    Custom ModelPatcher for managing the complete KaniTTS system in ComfyUI.
    Handles moving both the main transformer and the NeMo codec model to the
    correct device for inference and offloading to free VRAM.
    """
    def __init__(self, model, *args, **kwargs):
        super().__init__(model, *args, **kwargs)
        self.cache_key = f"{model.model_name}_{self.load_device.type}_{model.dtype}"

    @property
    def is_loaded(self) -> bool:
        return hasattr(self, 'model') and self.model is not None and self.model.model is not None

    def patch_model(self, device_to=None, *args, **kwargs):
        """
        Loads the entire KaniTTS system (transformer + codec) onto the target device.
        """
        target_device = self.load_device
        if not self.is_loaded:
            logger.info(f"Loading KaniTTS system '{self.model.model_name}' to {target_device}...")
            self.model.model = KaniTTSLoader.load_model(
                self.model.model_name, 
                target_device,
                self.model.dtype
            )

        # logger.info(f"KaniTTS system '{self.model.model_name}' is ready on {target_device}.")

        return super().patch_model(device_to=target_device, *args, **kwargs)

    def unpatch_model(self, device_to=None, unpatch_weights=True, *args, **kwargs):
        """
        Offloads both the KaniTTS transformer and the NeMo codec model.
        """
        if unpatch_weights:
            logger.info(f"Offloading KaniTTS system '{self.model.model_name}' to {self.offload_device}...")
            if self.is_loaded:
                kani_system = self.model.model
                kani_system.model.to(self.offload_device)
                
                if kani_system.player.audio_processor._model is not None:
                    kani_system.player.audio_processor._model.to(self.offload_device)
                
            self.model.model = None
            if self.cache_key in LOADED_MODELS_CACHE:
                del LOADED_MODELS_CACHE[self.cache_key]
                # logger.info(f"Cleared global model cache for: {self.cache_key}")
            
            gc.collect()
            model_management.soft_empty_cache()

        return super().unpatch_model(device_to, unpatch_weights, *args, **kwargs)