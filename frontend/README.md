# Triple Y · 通知转任务

把通知原文自动拆成截止时间、流程步骤、材料清单和待办任务。

## 本地运行
```bash
cd frontend
npm install
npm run dev
```
打开 http://localhost:5173

开发时 `/api` 由 Vite 同源代理到本机后端，前端不读取 API 环境变量。

## 功能
- 文字通知 / 截图 / PDF → AI 解析成结构化结果
- 任务清单：改名、完成/撤销、子任务、搜索、CSV 导出
- 日历：紧急/逾期圆点，点日期跳到对应任务
- 材料库 + RAG 追问（无依据会提示）
- 补充通知对比（原要求/新要求/受影响待办）
- 个人中心头像本地保存，响应式布局

## 目录
```
src/
  api2.ts           当前 API 层（保留 X-Session-Id）
  api2.js           渐进迁移兼容入口
  errors.ts         错误状态与 ErrorState
  state.ts          全局状态与持久化
  util.ts           Toast、按钮忙碌态、模态框可访问性
  components/
    AnalysisProgress.js  解析阶段
    InputPanel.js        输入、解析、对比、材料库
    ModeCard.js          结果展示（按需加载）
    Calendar.js          并行截止日
    TaskList.js          任务清单、历史、CSV
  tests/
docs/frontend/
```

## 工程命令

```bash
npm run typecheck
npm run lint
npm run test
npm run build
npm run ci
npm run capture:errors
```

## 前端文档

- `docs/frontend/engineering.md`
- `docs/frontend/error-states.md`
- `docs/frontend/performance.md`
- `docs/frontend/user-testing-kit.md`
- `docs/frontend/video-script.md`
