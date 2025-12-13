import os, hashlib, glob, pathlib, csv

def sha256_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for chunk in iter(lambda: f.read(1<<20), b''):
            h.update(chunk)
    return h.hexdigest()

def main():
    rows=[["sha256","label_id"]]
    for label_dir in sorted(glob.glob("seed/*")):
        label = pathlib.Path(label_dir).name
        for jpg in sorted(glob.glob(f"{label_dir}/*.jpg")):
            rows.append([sha256_file(jpg), label])
    os.makedirs("ops/eval", exist_ok=True)
    with open("ops/eval/gold_labels.csv","w",newline="") as f:
        csv.writer(f).writerows(rows)
    print({"ok":True, "wrote":"ops/eval/gold_labels.csv", "rows":len(rows)-1})

if __name__=="__main__":
    main()
