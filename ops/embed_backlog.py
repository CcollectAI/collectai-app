import os, json, boto3, io
from PIL import Image
from app.vision_index import load_model, load_index, save_index, embed_image, S3, BUCKET

def main():
    load_model(); load_index()
    lines = [json.loads(x) for x in open("ops/backlog.jsonl")]
    from app.vision_index import INDEX, META, caption_baseline
    added=0
    for r in lines:
        key = r["key"]
        obj = S3.get_object(Bucket=BUCKET, Key=key)
        data = obj["Body"].read()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        vec = embed_image(img)
        INDEX.add(vec)
        META.append({"sha256": r["sha256"], "key": key, "caption": caption_baseline(), "dim":512})
        added+=1
    if added: save_index()
    print(f"embedded {added}")
if __name__=="__main__": main()
