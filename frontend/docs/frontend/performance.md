# 性能与可访问性

## 测试环境

- Git 基线：`b24e56b`
- Chrome headless
- Lighthouse 12
- 基线地址：`http://127.0.0.1:4174/`
- 改后地址：`http://127.0.0.1:4173/`
- 均使用生产构建，不再对比 Vite 开发服务器

## 前后对比

| 指标 | 改动前 | 改动后 |
| --- | ---: | ---: |
| Performance | 99 | 100 |
| Accessibility | 83 | 93 |
| FCP | 1.4 s | 1.4 s |
| LCP | 1.6 s | 1.5 s |
| CLS | 0 | 0 |
| TBT | 40 ms | 0 ms |
| Speed Index | 3.2 s | 1.6 s |

## 本轮改动

- 开屏只在同一会话第一次显示，自动关闭时间从 1.8 秒降到 650 ms，点击可立即跳过。
- `ModeCard` 结果展示改为按需动态加载。
- 用户弹窗继续保持按需加载。
- 头像图片使用 `loading="lazy"` 和 `decoding="async"`。
- 保留 `prefers-reduced-motion`。
- 错误和解析进度增加 `aria-live`。
- 补齐键盘焦点样式、弹窗焦点陷阱和关闭后的焦点返回。

## 报告

- `docs/frontend/lighthouse/before-prod.report.html`
- `docs/frontend/lighthouse/after-prod.report.html`
- `docs/frontend/lighthouse/before-prod.report.json`
- `docs/frontend/lighthouse/after-prod.report.json`
- `docs/frontend/lighthouse/before-prod.png`
- `docs/frontend/lighthouse/after-prod.png`
