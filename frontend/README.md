# Triple Y · 通知转任务

把通知原文自动拆成截止时间、流程步骤、材料清单和待办任务。

## 本地运行
```bash
cd frontend
npm install
$env:VITE_API_BASE_URL="http://localhost:8000"
npm run dev
```
打开 http://localhost:5173

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
  api.js            接口封装（带 X-Session-Id）
  state.js         全局状态
  components/
    ProfileCard.js  用户卡片
    Calendar.js     月历
    InputPanel.js   输入+解析+材料库+追问
    ModeCard.js     结果卡片渲染
    TaskList.js     任务清单+历史+搜索+导出
    UserModal.js    个人中心
```
