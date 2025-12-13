import os, json, pickle
from app.vision_labels import load_labels, text_prompts
from app.vision_embed import get_text_embed_matrix

def main():
    load_labels(os.getenv("VISION_LABELS_PATH","ops/vision_labels.json"))
    T = get_text_embed_matrix(text_prompts())   # (N,512)
    os.makedirs("ops/cache", exist_ok=True)
    with open("ops/cache/label_text_matrix.pkl","wb") as f:
        pickle.dump(T, f)
    print({"ok": True, "rows": len(text_prompts()), "out": "ops/cache/label_text_matrix.pkl"})

if __name__ == "__main__":
    main()
