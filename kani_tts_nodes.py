import torch
import gc
import logging
import sys
from typing import cast

import comfy.model_management as model_management
from comfy_api.latest import ComfyExtension, io, ui

from .modules.model_info import AVAILABLE_KANI_MODELS, SPEAKERS_370M
from .modules.loader import KaniTTSModelHandler
from .modules.patcher import KaniTTSPatcher

logger = logging.getLogger(__name__)

KANI_PATCHER_CACHE = {}

def get_available_devices():
    """Detects and returns a list of available PyTorch devices."""
    devices = []
    if torch.cuda.is_available():
        devices.append("cuda")
    if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
        devices.append("mps")
    devices.append("cpu")
    return devices

def set_seed(seed: int):
    if seed < 0:
        seed = torch.randint(0, sys.maxsize, (1,)).item()
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

class KaniTTSNode(io.ComfyNode):
    CATEGORY = "audio/tts"

    @classmethod
    def define_schema(cls) -> io.Schema:
        model_names = sorted(list(AVAILABLE_KANI_MODELS.keys()))
        if not model_names:
            model_names.append("No models found. Please restart ComfyUI.")

        available_devices = get_available_devices()
        default_device = available_devices[0]
        
        available_dtypes = ["bfloat16", "float16", "float32"]
        default_dtype = "bfloat16"
        if default_device == "mps" and default_dtype not in ["float16", "float32"]:
            default_dtype = "float16"

        return io.Schema(
            node_id="KaniTTS",
            display_name="Kani TTS",
            category=cls.CATEGORY,
            description="Generate speech using the KaniTTS model.",
            inputs=[
                io.Combo.Input("model_name", options=model_names, default=model_names[0], tooltip="Select the KaniTTS model to use. The 370m model supports speakers."),
                io.Combo.Input("speaker", options=SPEAKERS_370M, default="None", tooltip="Select a speaker. Only works with the 370m model."),
                io.String.Input("text", multiline=True, default="Hello world! My name is Kani, I'm a speech generation model!", tooltip="Text to synthesize."),
                io.Float.Input("temperature", default=1.4, min=0.1, max=2.0, step=0.05, tooltip="Controls randomness. Higher values are more creative."),
                io.Float.Input("top_p", default=0.95, min=0.1, max=1.0, step=0.05, tooltip="Nucleus sampling probability."),
                io.Float.Input("repetition_penalty", default=1.1, min=1.0, max=2.0, step=0.05, tooltip="Penalty for repeating tokens."),
                io.Int.Input("max_new_tokens", default=1200, min=100, max=2000, step=50, tooltip="Maximum number of audio tokens to generate."),
                io.Int.Input("seed", default=-1, min=-1, max=0xFFFFFFFFFFFFFFFF, tooltip="Seed for reproducibility. -1 for random."),
                io.Boolean.Input("force_offload", default=False, label_on="Force Offload", label_off="Auto-Manage", tooltip="Force the model to be offloaded from VRAM after generation."),
                io.Combo.Input("device", options=available_devices, default=default_device, tooltip="Device to run inference on."),
                io.Combo.Input("dtype", options=available_dtypes, default=default_dtype, tooltip="Precision for the model. bfloat16 is fastest on supported GPUs."),
            ],
            outputs=[
                io.Audio.Output(display_name="Generated Audio"),
            ],
        )

    @classmethod
    def execute(
        cls,
        model_name: str,
        speaker: str,
        text: str,
        temperature: float,
        top_p: float,
        repetition_penalty: float,
        max_new_tokens: int,
        seed: int,
        force_offload: bool,
        device: str,
        dtype: str,
    ) -> io.NodeOutput:
        
        if not text.strip():
            raise ValueError("Text input cannot be empty.")

        if device == "cuda":
            load_device = model_management.get_torch_device()
            offload_device = model_management.intermediate_device()
        else:
            load_device = torch.device(device)
            offload_device = torch.device("cpu")
        
        if load_device.type == "mps" and dtype not in ["float16", "float32"]:
            logger.warning(f"Unsupported dtype '{dtype}' for MPS, falling back to float16.")
            dtype = "float16"

        cache_key = f"{model_name}_{device}_{dtype}"
        if cache_key not in KANI_PATCHER_CACHE:
            handler = KaniTTSModelHandler(model_name, dtype)
            patcher = KaniTTSPatcher(
                handler,
                load_device=load_device,
                offload_device=offload_device,
            )
            KANI_PATCHER_CACHE[cache_key] = patcher
        
        patcher = KANI_PATCHER_CACHE[cache_key]
        
        model_management.load_model_gpu(patcher)
        kani_model = patcher.model.model

        if not kani_model:
            raise RuntimeError(f"Failed to load KaniTTS model '{model_name}'. Check logs for details.")

        set_seed(seed)
        
        kani_model.config.model.temperature = temperature
        kani_model.config.model.top_p = top_p
        kani_model.config.model.repetition_penalty = repetition_penalty
        kani_model.config.model.max_new_tokens = max_new_tokens

        model_info = AVAILABLE_KANI_MODELS.get(model_name, {})
        speaker_id = None
        if "speakers" in model_info and speaker != "None":
            speaker_id = speaker.split(" -- ")[0].strip()
            logger.info(f"Using speaker: {speaker_id}")
        elif speaker != "None":
            logger.warning(f"Speaker '{speaker}' selected, but model '{model_name}' does not support speakers. This setting will be ignored.")

        try:
            logger.info("Generating audio...")
            wav_array, _ = kani_model.run_model(text, speaker_id=speaker_id)

            output_tensor = torch.from_numpy(wav_array).float().unsqueeze(0).unsqueeze(0) # Shape becomes (1, 1, num_samples)

            sample_rate = kani_model.config.audio.sample_rate
            output_audio = {"waveform": output_tensor, "sample_rate": sample_rate}

            # logger.info("Audio generation complete.")

            if force_offload:
                logger.info(f"Force offloading KaniTTS model '{model_name}' from VRAM...")
                patcher.unpatch_model(unpatch_weights=True)
                
            return io.NodeOutput(output_audio, ui=ui.PreviewAudio(output_audio, cls=cls))

        except Exception as e:
            logger.error(f"Error during KaniTTS generation: {e}")
            raise e