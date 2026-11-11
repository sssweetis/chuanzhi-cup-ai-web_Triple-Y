# 环境变量说明

C 需要配置以下环境变量，用于接通大模型 API 与本地调试：

| 变量名 | 必填 | 说明 | 示例 |
|---|---|---|---|
| `LLM_API_KEY` | 是（生产） | 大模型 API Key | `sk-xxxxxxxx` |
| `LLM_BASE_URL` | 否 | API 地址；团队正式使用 DeepSeek | `https://api.deepseek.com` |
| `LLM_MODEL` | 否 | API model ID；团队正式使用 `deepseek-flash` | `deepseek-flash` |
| `LLM_ENABLE_MOCK` | 否 | 本地联调时设为 `1`，无 Key 也能跑通 | `1`（仅开发） |

> **生产环境不要设置 `LLM_ENABLE_MOCK`。**
> 模型 ID 以 API `/models` 返回为准；`deepseek-chat` 只是兼容别名，团队统一配置 `deepseek-flash`。

---

## 在 Windows 中配置环境变量

### 方式一：临时设置（当前 PowerShell 窗口有效）

1. 打开 PowerShell。
2. 执行以下命令：

   ```powershell
   # 生产或联调（走真实大模型）
   $env:LLM_API_KEY="sk-xxxxxxxx"
   $env:LLM_BASE_URL="https://api.deepseek.com"
   $env:LLM_MODEL="deepseek-flash"

   # 开发环境（无 Key，用 Mock 数据）
   $env:LLM_ENABLE_MOCK="1"
   ```

3. 关闭窗口后失效，适合临时测试。

### 方式二：永久设置（用户级，推荐）

1. 打开 PowerShell。
2. 执行以下命令（每个变量单独执行）：

   ```powershell
   setx LLM_API_KEY "sk-xxxxxxxx"
   setx LLM_BASE_URL "https://api.deepseek.com"
   setx LLM_MODEL "deepseek-flash"
   ```

3. 设置完成后，**需要新开一个 PowerShell 窗口**才能生效。
4. 如需删除变量，执行：

   ```powershell
   setx LLM_API_KEY ""
   ```

### 方式三：通过系统界面设置

1. 右键“此电脑” → “属性” → “高级系统设置”。
2. 点击“环境变量”。
3. 在“用户变量”或“系统变量”中点击“新建”。
4. 依次填入变量名和值。
5. 确定后**重启终端**。

### 方式四：使用 `.env` 文件（推荐开发时使用）

1. 在项目根目录创建 `.env` 文件。
2. 写入以下内容：

   ```env
   LLM_API_KEY=sk-xxxxxxxx
   LLM_BASE_URL=https://api.deepseek.com
   LLM_MODEL=deepseek-flash
   ```

3. 如果程序使用 `python-dotenv`，在启动脚本中加载：

   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```

---

## 验证配置是否生效

1. 在 `service.py` 所在目录打开 PowerShell。
2. 执行以下命令：

   ```powershell
   python -c "from service import analyze_notification; import json; print(json.dumps(analyze_notification('请于10月25日18:00前提交奖学金报名表。'), ensure_ascii=False, indent=2))"
   ```

3. 如果返回带 `title` 和 `deadline` 的 JSON，说明配置成功。

---

## 常见问题

1. **没配 `LLM_API_KEY`，但设了 `LLM_ENABLE_MOCK=1`**  
   系统会返回 Mock 数据，用于前端 UI 联调。**不要**在生产使用。

2. **`LLM_BASE_URL` 填错了**  
   会报网络连接错误。团队正式值为 `https://api.deepseek.com`。  
   如果使用其他代理或平台，请填写对应的 Base URL。

3. **模型名称 `LLM_MODEL` 填错**  
   接口会返回“模型不存在”错误。请确认当前 API Key 支持所填模型。

4. **设置了环境变量但程序读不到**  
   - 确保设置后重启了 PowerShell 或 IDE。  
   - 如果用 `setx`，需要新开窗口才能生效。  
   - 如果用 `.env`，确认程序已调用 `load_dotenv()`。