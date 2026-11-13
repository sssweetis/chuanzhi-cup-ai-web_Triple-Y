const STAGES = [
  { key: 'upload', label: '上传与读取', detail: '准备通知内容' },
  { key: 'extract', label: 'OCR / PDF 提取', detail: '识别文字与时间点' },
  { key: 'llm', label: '大模型解析', detail: '拆分任务和材料' },
  { key: 'schema', label: 'Schema 校验', detail: '检查字段是否完整' },
  { key: 'date', label: '日期核对', detail: '检查截止时间是否合理' },
  { key: 'complete', label: '完成', detail: '生成可执行清单' },
]

export function renderAnalysisProgress(container, options) {
  const { stage = 'upload', onCancel } = options
  const currentIndex = Math.max(
    0,
    STAGES.findIndex((item) => item.key === stage),
  )
  container.innerHTML = `
    <div class="analysis-progress" role="status" aria-live="polite" aria-label="正在解析通知">
      <div class="analysis-progress-head">
        <div>
          <b>正在整理通知</b>
          <span>文件上传后会依次完成识别、解析和日期核对</span>
        </div>
        <button class="btn btn-ghost btn-sm" type="button" data-cancel-analysis>取消</button>
      </div>
      <div class="analysis-stage-list">
        ${STAGES.map((item, index) => {
          const status = index < currentIndex ? 'is-done' : index === currentIndex ? 'is-current' : ''
          return `
            <div class="analysis-stage ${status}">
              <span class="analysis-stage-mark" aria-hidden="true">${index < currentIndex ? '✓' : index + 1}</span>
              <div><b>${item.label}</b><small>${item.detail}</small></div>
              ${index === currentIndex ? '<span class="spinner spinner-dark stage-spinner" aria-hidden="true"></span>' : ''}
            </div>`
        }).join('')}
      </div>
      <div class="analysis-progress-foot">
        <div class="analysis-progress-track"><i style="width:${Math.round(((currentIndex + 1) / STAGES.length) * 100)}%"></i></div>
        <span>通常需要 10–30 秒。超过 90 秒会提供继续等待或更换输入。</span>
      </div>
    </div>`
  container.querySelector('[data-cancel-analysis]').onclick = () => onCancel?.()
}

export const ANALYSIS_STAGES = STAGES
