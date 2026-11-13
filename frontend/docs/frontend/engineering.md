# 前端工程说明

## 技术边界

- Vite 5 + 原生 JavaScript + CSS
- 不引入 React、Vue、UI 框架或状态库
- 渐进 TypeScript，不重写现有 UI
- 当前活动 API 层为 `src/api2.ts`，`src/api.ts` 提供 typed alias；旧 `api.js` 保留不参与构建

## 组件树

```text
main.js
├─ ProfileCard
│  └─ UserModal（按需加载）
├─ Calendar
├─ InputPanel
│  ├─ AnalysisProgress
│  ├─ ModeCard（按需加载）
│  └─ ErrorState
└─ TaskList
   └─ 历史清空确认 Modal
```

## 状态管理

`state.ts` 保留 `zhiban-state-v2` 持久化键，只持久化：

- `profile`
- `tasks`
- `analyzeResult`
- `activeTab`

解析阶段、错误、慢请求提示属于临时状态，不写入 localStorage。

`setState(patch, { notify: false })` 用于解析中的进度刷新，避免每一步都重建输入框和丢失文件选择。

## 解析状态机

```text
preparing
  -> upload
  -> extract
  -> llm
  -> schema
  -> date
  -> complete
  -> success

任意阶段 -> cancelled
任意阶段 -> error -> retry / edit / reupload / help
90 秒 -> slow warning -> continue / retry / edit
```

- 每轮解析使用独立 `AbortController`
- `activeAnalysis` 阻止重复请求
- 取消后恢复可编辑状态，并保留文字和文件选择
- 90 秒只显示提示，不自动中止仍在处理的请求

## 类型与测试

- `npm run typecheck`：TypeScript 核心与兼容 JS 类型检查
- `npm run lint`：ESLint
- `npm run test`：Vitest + jsdom
- `npm run ci`：类型、Lint、测试、构建串行执行
- `npm run format:check`：Prettier

当前 22 个测试覆盖：

- 12 个用户错误场景
- 取消请求
- 90 秒慢请求提示
- 429 映射
- `X-Session-Id`
- localStorage 恢复
- 日期边界
- 空结果
- ErrorState aria-live

## 可访问性

- 错误 `role="alert"` + `aria-live="assertive"`
- 解析进度 `role="status"` + `aria-live="polite"`
- 弹窗 `role="dialog"` + `aria-modal="true"`
- Tab 焦点陷阱
- Esc 关闭
- 关闭后焦点返回触发按钮
- 键盘焦点样式
- 尊重 `prefers-reduced-motion`
