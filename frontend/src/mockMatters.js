// A 给的三份示例 JSON（写死作演示，接真接口后替换数据源即可）
export const sampleSimple = {
  schema_version: '1.0', mode: 'simple', mode_source: 'auto',
  complexity_score: 0.2, detected_features: ['has_deadline'],
  enabled_sections: ['summary', 'schedule', 'source'],
  title: '提交奖学金报名表', priority: 'medium', status: 'not_started',
  status_source: 'auto', timezone: 'Asia/Shanghai', created_at: '', updated_at: '',
  deadline: { scope: 'overall', label: '截止时间', due_at: '2026-10-25T18:00:00+08:00', all_day: false,
    source_ref: { quote: '请于10月25日18:00前提交' } },
  reminders: [{ reminder_id: 'rem_1', offset_minutes: 120, channels: ['app'], enabled: true }],
  sources: [{ quote: '请于10月25日18:00前提交', page: null }]
}

export const sampleStandard = {
  schema_version: '1.0', mode: 'standard', mode_source: 'auto',
  complexity_score: 0.5,
  detected_features: ['has_deadline', 'has_multiple_steps', 'has_materials', 'has_attachments', 'has_location'],
  enabled_sections: ['summary', 'schedule', 'content', 'steps', 'materials', 'source'],
  title: '奖学金报名材料提交', priority: 'medium', status: 'not_started',
  status_source: 'auto', timezone: 'Asia/Shanghai', created_at: '', updated_at: '',
  deadline: { scope: 'overall', label: '截止时间', due_at: '2026-10-25T18:00:00+08:00',
    source_ref: { quote: '10月25日18:00前提交' } },
  reminders: [{ reminder_id: 'rem_1', offset_minutes: 120, channels: ['app'], enabled: true }],
  default_location: { type: 'offline', name: '行政楼302', room: '302', source_ref: { quote: '交至行政楼302' } },
  key_points: ['需本人签字'],
  attachments: [{ attachment_id: 'att_1', attachment_name: '报名表', attachment_type: 'file', source_ref: { quote: '附件1' } }],
  materials: [
    { material_id: 'mat_1', material_name: '报名表', material_type: 'required', status: 'pending', template_attachment_id: 'att_1', source_ref: { quote: '提交报名表（附件1）' } },
    { material_id: 'mat_2', material_name: '成绩单', material_type: 'required', status: 'pending', source_ref: { quote: '成绩单' } },
    { material_id: 'mat_3', material_name: '身份证复印件', material_type: 'required', status: 'pending', source_ref: { quote: '身份证复印件' } }
  ],
  step_list: [
    { step_id: 'step_1', order: 1, title: '准备报名材料', status: 'not_started', due_at: '2026-10-25T18:00:00+08:00',
      due_at_inherited_from: 'overall', key_points: ['需本人签字'], materials: ['mat_1', 'mat_2', 'mat_3'], attachments: ['att_1'],
      source_ref: { quote: '提交报名表（附件1）、成绩单、身份证复印件' } },
    { step_id: 'step_2', order: 2, title: '交至行政楼302', status: 'not_started', due_at: '2026-10-25T18:00:00+08:00',
      due_at_inherited_from: 'overall', location: { type: 'offline', name: '行政楼302', room: '302' },
      source_ref: { quote: '交至行政楼302' } }
  ],
  sources: [{ quote: '奖学金报名：10月25日18:00前提交报名表（附件1）、成绩单、身份证复印件，交至行政楼302，需本人签字。', page: null }]
}

export const sampleComplex = {
  schema_version: '1.0', mode: 'complex', mode_source: 'auto',
  complexity_score: 0.9,
  detected_features: ['has_deadline', 'has_multiple_steps', 'has_sub_steps', 'has_materials', 'has_attachments', 'has_review', 'has_dependencies'],
  enabled_sections: ['summary', 'schedule', 'content', 'steps', 'materials', 'warnings', 'governance', 'source'],
  title: '奖学金报名流程', priority: 'medium', status: 'not_started',
  status_source: 'auto', timezone: 'Asia/Shanghai', created_at: '', updated_at: '',
  deadline: { scope: 'overall', label: '截止时间', start_at: '2026-10-20T00:00:00+08:00', due_at: '2026-11-01T23:59:59+08:00',
    source_ref: { quote: '10月20日-25日在线填写报名表' } },
  reminders: [{ reminder_id: 'rem_1', offset_minutes: 120, channels: ['app'], enabled: true }],
  attachments: [{ attachment_id: 'att_1', attachment_name: '报名表', attachment_type: 'file', source_ref: { quote: '附件1' } }],
  materials: [
    { material_id: 'mat_1', material_name: '报名表', material_type: 'required', status: 'pending', template_attachment_id: 'att_1', source_ref: { quote: '在线填写报名表（附件1）' } },
    { material_id: 'mat_2', material_name: '身份证', material_type: 'required', status: 'pending', source_ref: { quote: '上传身份证' } },
    { material_id: 'mat_3', material_name: '成绩单', material_type: 'required', status: 'pending', source_ref: { quote: '上传成绩单' } }
  ],
  step_list: [
    { step_id: 'step_1', order: 1, title: '在线填写报名表', status: 'not_started', start_at: '2026-10-20T00:00:00+08:00', due_at: '2026-10-25T23:59:59+08:00',
      materials: ['mat_1'], attachments: ['att_1'],
      sub_step_list: [
        { sub_step_id: 'sub_1_1', parent_id: 'step_1', order: 1, title: '下载报名表模板', status: 'not_started', source_ref: { quote: '附件1' } },
        { sub_step_id: 'sub_1_2', parent_id: 'step_1', order: 2, title: '填写并上传', status: 'not_started', source_ref: { quote: '在线填写报名表' } }
      ],
      source_ref: { quote: '10月20日-25日在线填写报名表（附件1）' } },
    { step_id: 'step_2', order: 2, title: '材料审核', status: 'not_started', start_at: '2026-10-26T00:00:00+08:00', due_at: '2026-10-28T23:59:59+08:00',
      owner: { name: '王老师' }, review: { required: true, reviewer: { name: '王老师' }, status: 'pending' },
      dependencies: [{ type: 'finish_to_start', step_id: 'step_1' }], source_ref: { quote: '10月26-28日王老师审核' } },
    { step_id: 'step_3', order: 3, title: '缴费', status: 'not_started', start_at: '2026-10-29T00:00:00+08:00', due_at: '2026-10-30T23:59:59+08:00',
      condition: '审核通过后', dependencies: [{ type: 'finish_to_start', step_id: 'step_2' }], source_ref: { quote: '10月29-30日缴费100元' } },
    { step_id: 'step_4', order: 4, title: '打印准考证', status: 'not_started', start_at: '2026-11-01T00:00:00+08:00', due_at: '2026-11-01T23:59:59+08:00',
      dependencies: [{ type: 'finish_to_start', step_id: 'step_3' }], source_ref: { quote: '11月1日打印准考证' } }
  ],
  warning_list: [{ warning_id: 'warn_1', warning_type: 'deadline_risk', mode_scope: 'complex', severity: 'medium',
    message: '步骤3缴费与步骤2审核间隔仅1天，请提前准备', rule: { related_step_ids: ['step_2', 'step_3'] },
    action: { type: 'notify', suggestion: '建议审核通过后立即缴费' } }],
  sources: [{ quote: '奖学金报名流程：10月20日-25日在线填写报名表（附件1），上传身份证和成绩单；10月26-28日王老师审核，审核通过后才能缴费；10月29-30日缴费100元；11月1日打印准考证。', page: null }]
}

export const SAMPLES = [
  { label: '示例 · 极简', data: sampleSimple },
  { label: '示例 · 标准', data: sampleStandard },
  { label: '示例 · 完整流程', data: sampleComplex }
]
