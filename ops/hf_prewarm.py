import logging

from transformers import AutoProcessor, CLIPModel

logger = logging.getLogger(__name__)

m = "openai/clip-vit-base-patch32"
AutoProcessor.from_pretrained(m)
CLIPModel.from_pretrained(m)
logger.info("HF cache warmed for %s", m)
