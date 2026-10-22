import base64
from service import analyze_notification_from_image

with open(r"测试用图.png", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()
uri = f"data:image/png;base64,{b64}"

res = analyze_notification_from_image(uri)
if res["success"]:
    d = res["data"]
    print("标题:", d.get("title"))
    print("靠看清单 confirmation_needed:", d.get("confirmation_needed"))
    print("材料:", [m.get("material_name") for m in d.get("materials", [])])
else:
    print("失败:", res["error"])