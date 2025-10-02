"""Factory for creating TTS system components."""

from typing import Optional, Tuple
from .config import Config
from .audio import NemoAudioPlayer
from .models import KaniModel


class TTSFactory:
    """Factory for creating TTS system components."""
    
    @staticmethod
    def create_system(config: Optional[Config] = None, codec_model=None) -> Tuple[KaniModel, NemoAudioPlayer]:
        """
        Create a complete TTS system.
        Accepts an optional pre-loaded codec_model to use instead of loading a new one.
        """
        if config is None:
            config = Config.default()
        
        # Pass the pre-loaded codec model to the player
        player = NemoAudioPlayer(config, codec_model=codec_model)
        model = KaniModel(config, player)
        
        return model, player