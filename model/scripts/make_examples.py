import json, random, cv2, numpy as np
from pathlib import Path
H=Path(__file__).resolve().parent; SRC=H.parent/"Footage Sources"
d=json.load(open(H/"tiles/puget_v1/valid/_annotations.coco.json"))
by={}
for a in d["annotations"]: by.setdefault(a["image_id"],[]).append(a)
im=[i for i in d["images"] if i["wb_gray_world"] and i["id"] in by]
random.Random(3).shuffle(im)
rows=[]; col={0:(0,255,0),1:(255,0,255)}
for i in im[:4]:
    x0,y0=i["tile_xy"]; raw=cv2.imread(str(SRC/"Puget Sound LILA/images"/i["source"]))[y0:y0+512,x0:x0+512].copy()
    wb=cv2.imread(str(H/"tiles/puget_v1/valid"/i["file_name"]))
    for im_ in (raw,wb):
        for a in by[i["id"]]:
            x,y,w,h=[int(v) for v in a["bbox"]]; cv2.rectangle(im_,(x,y),(x+w,y+h),col[a["category_id"]],2)
    rows.append(np.hstack([raw,wb])); print(i["file_name"],[a["category_id"] for a in by[i["id"]]], "raw mean BGR",raw.reshape(-1,3).mean(0).round(0),"wb",wb.reshape(-1,3).mean(0).round(0))
cv2.imwrite(str(H/"examples/wb_before_after_val.jpg"),np.vstack(rows[:2])); cv2.imwrite(str(H/"examples/wb_before_after_val2.jpg"),np.vstack(rows[2:]))
