# 智办 · 前端（frontend/）

## 怎么跑
```bash
npm install
npm run dev      # 开发，默认 http://localhost:5173
npm run build    # 产出 dist/
npm run preview  # 预览构建产物
```

## 接口对接（和 C 对齐）
- 统一封装在 `src/api.js`：`analyzeNotification(text)` → `POST /api/analyze`
- `POST /api/analyze` 请求体：`{ "text": "通知原文" }`（字段名统一为 `text`）
- 返回：Matter 对象（含 `mode` / `enabled_sections` / `title` / `deadline` / `materials[]` / `step_list[]` 等，按 A 的 schema）
- 后端地址在 `.env.development` 的 `VITE_API_BASE_URL`，联调时改
- fetch 超时统一 60s（真实解析 10~30s，不能更短）
- `POST /api/check` 入参：
```json
{
  "notification_id": "通知id",
  "profile": { "team_size": 3, "has_doc": true, "has_video": false, "has_teacher_confirm": null },
  "checked_material_ids": ["m1", "m2"]
}
```

## 渲染约定
- 按返回的 `data.mode` 渲染：`simple` 不出 materials/steps（设计如此，不是缺字段）；`standard` 加材料/地点；`complex` 加流程步骤/预警
- 解析中有骨架屏 loading，失败有错误文案 + 重试按钮
- 用户中心弹窗懒加载（动态 import，首屏不加载）

## 目录
```
src/
  api.js            接口封装
  state.js         极简全局状态
  components/
    ProfileCard.js  用户卡片
    Calendar.js     月历
    InputPanel.js   输入通知 + AI 解析
    ModeCard.js     按 mode 渲染结果卡片
    TaskList.js     任务清单 + 历史
    CheckForm.js    10/18 用户情况填写
    UserModal.js    个人中心（懒加载）
```
