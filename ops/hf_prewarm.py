from transformers import AutoProcessor, CLIPModel
m = "openai/clip-vit-base-patch32"
AutoProcessor.from_pretrained(m)
CLIPModel.from_pretrained(m)
print("HF cache warmed for", m)
