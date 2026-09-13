import csv, json

rows = []
with open(r"C:\Users\pi\claude\pipeline_runs.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        out = {}
        for k, v in row.items():
            if v == "":
                out[k] = None
            elif k in ("IsRetrim", "Excluded", "Failed"):
                out[k] = v == "True"
            else:
                try:
                    out[k] = int(v)
                except ValueError:
                    try:
                        out[k] = float(v)
                    except ValueError:
                        out[k] = v
        rows.append(out)

with open(r"C:\Users\pi\claude\pipeline_runs.json", "w", encoding="utf-8") as f:
    json.dump(rows, f, indent=2)

print(f"Restored {len(rows)} records to pipeline_runs.json")
