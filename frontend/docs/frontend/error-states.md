# ErrorState 错误体验

实现位置：

- `src/errors.ts`：错误码、用户文案、请求异常归一化、ErrorState 渲染
- `src/errors.js`：渐进迁移兼容入口
- `error-lab.html`：错误场景视觉验收页
- `src/components/AnalysisProgress.js`：解析阶段进度与取消

## 设计规则

每张错误卡固定包含：

1. 用户能理解的标题
2. 一句人话描述
3. 明确的下一步
4. 可恢复操作：继续等待、重试、换文字、重新上传、查看帮助
5. 复制错误编号

错误卡使用 `role="alert"` 和 `aria-live="assertive"`。后端 `error` 原文只用于内部识别，不直接显示给用户。

## 12 个场景

| 编号 | 场景 | 用户动作 |
| --- | --- | --- |
| 01 | 离线 | 恢复网络后重试，或换文字 |
| 02 | 网络连接失败 | 重试、换文字、复制错误编号 |
| 03 | 90 秒处理较慢 | 继续等待、重试、换文字 |
| 04 | 429 请求频繁 | 等待后重试 |
| 05 | 413 文件过大 | 重新上传 |
| 06 | 415 格式不支持 | 重新上传或换文字 |
| 07 | 扫描版 PDF | 截图或粘贴文字 |
| 08 | 空结果 | 补充上下文或换文字 |
| 09 | 模型凭证不可用 | 查看帮助、使用示例 |
| 10 | OCR 不可用 | 重新上传或粘贴文字 |
| 11 | 服务临时异常 | 重试、复制错误编号 |
| 12 | 返回结构不完整 | 重试或换文字 |

## 验收截图

截图位于 `docs/frontend/screenshots/errors/`：

1. `01-offline.png`
2. `02-network.png`
3. `03-timeout.png`
4. `04-rate_limited.png`
5. `05-file_too_large.png`
6. `06-unsupported_media.png`
7. `07-scanned_pdf.png`
8. `08-empty_result.png`
9. `09-auth.png`
10. `10-ocr_unavailable.png`
11. `11-server_error.png`
12. `12-invalid_response.png`

重新生成：

```powershell
npm run dev
npm run capture:errors
```
