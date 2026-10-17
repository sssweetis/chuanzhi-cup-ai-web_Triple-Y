# 前端（B 负责）

后端接口已经就绪，前端页面放在这个目录。

## 接入三步

1. 本目录建前端项目（React + Vite / Vue 3 + Vite 均可）
2. 根目录 `.env.local` 写后端地址：

   ```env
   VITE_API_BASE_URL=http://127.0.0.1:8000
   ```

3. 复制 `../backend/for-frontend/api.js` 到前端 `src/api/notice.js`，调用 `analyzeNotice(text)`

## 接口速记

- `POST /api/analyze`，请求 `{ "text": "通知原文" }`
- 响应恒定 HTTP 200 + `{ success, data, error }`，判断 `success` 即可
- `data.mode` = `simple` / `standard` / `complex`，按模式决定渲染「材料清单 / 步骤 / 风险预警」等区块
- 跨域已放开，不用配代理

详细字段结构见 [../docs/接口契约.md](../docs/接口契约.md)，后端启动与联调见 [../backend/README.md](../backend/README.md)。