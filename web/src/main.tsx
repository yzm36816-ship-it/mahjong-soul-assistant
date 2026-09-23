import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

type Session = { id: string; mode: number | null; event_count: number; round_count: number; synthetic: boolean; updated_at: string }
type Event = { session_id: string; sequence: number; round_index: number; kind: string; seat: string | null; tile: string | null; source: string; confidence: string; note: string; observed_at: string }
type Metrics = { mode: number; promoted: boolean; reason: string; sources?: Record<string, number>; samples?: Record<string, number>; games?: Record<string, number>; tenpai?: { model: { brier: number; ece: number; precision: number; recall: number }; rule_bucket_baseline: { brier: number } }; waits?: { model_recall_at_5: number | null; prior_recall_at_5: number | null; examples: number }; ron?: { model_brier: number | null; prior_brier: number | null; examples: number } }
type Review = { answer: string; evidence: number[]; limitations: string }
type CaseData = { gaps: Event[]; corrections: Array<{ id: number; session_id: string; sequence: number; field: string; corrected_value: string; note: string }> }

const labels: Record<string, string> = {
  round_start: '新一局', midround_join: '中途接入', discard: '舍牌',
  riichi_candidate: '疑似立直', riichi_confirmed: '确认立直', call_confirmed: '确认副露',
  river_removed_candidate: '牌河减少', tracking_gap: '跟踪缺口',
}
const seats: Record<string, string> = { self: '自己', left: '左侧', top: '上方', right: '右侧' }
const honors: Record<string, string> = { '1z': '东', '2z': '南', '3z': '西', '4z': '北', '5z': '白', '6z': '发', '7z': '中' }
function tileName(tile: string | null) {
  if (!tile) return ''
  return honors[tile] ?? `${tile[0]}${{m: '万', p: '筒', s: '索'}[tile[1] as 'm' | 'p' | 's'] ?? ''}`
}
async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) throw new Error(`${response.status} · ${await response.text()}`)
  return response.json() as Promise<T>
}
function percentage(value: number | null | undefined) { return value == null ? '—' : `${Math.round(value * 100)}%` }
function decimal(value: number | null | undefined) { return value == null ? '—' : value.toFixed(3) }

function App() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [selected, setSelected] = useState('demo-3p')
  const [events, setEvents] = useState<Event[]>([])
  const [eventNumber, setEventNumber] = useState<number | null>(null)
  const [metrics, setMetrics] = useState<Record<string, Metrics>>({})
  const [cases, setCases] = useState<CaseData>({ gaps: [], corrections: [] })
  const [question, setQuestion] = useState('这一巡发生了什么？')
  const [reply, setReply] = useState<Review | null>(null)
  const [correction, setCorrection] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const chosen = sessions.find(session => session.id === selected)
  const current = events.find(event => event.sequence === eventNumber) ?? events.at(-1)
  const activeNumber = current?.sequence ?? null

  useEffect(() => {
    Promise.all([api<Session[]>('/api/sessions'), api<Record<string, Metrics>>('/api/metrics'), api<CaseData>('/api/cases')])
      .then(([allSessions, allMetrics, allCases]) => { setSessions(allSessions); setMetrics(allMetrics); setCases(allCases); setSelected(old => allSessions.some(session => session.id === old) ? old : allSessions[0]?.id ?? '') })
      .catch(reason => setError(`无法连接本地看板服务：${reason}`))
  }, [])
  useEffect(() => {
    if (!selected) return
    api<Event[]>(`/api/sessions/${selected}/events`)
      .then(rows => { setEvents(rows); setEventNumber(rows.at(-1)?.sequence ?? null); setReply(null); setError('') })
      .catch(reason => setError(`读取牌局失败：${reason}`))
  }, [selected])

  async function ask() {
    try {
      const result = await api<Review>('/api/review', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ session_id: selected, sequence: activeNumber, question }) })
      setReply(result)
    } catch (reason) { setError(`复盘失败：${reason}`) }
  }
  async function correct() {
    if (!current || !correction.trim()) return
    try {
      const result = await api<{ id: number }>('/api/corrections', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ session_id: selected, sequence: current.sequence, field: 'tile', corrected_value: correction.trim(), note: 'Web 复盘人工修正' }) })
      setMessage(`修正 #${result.id} 已保存在本机；原始事件保持可追溯。`)
      setCorrection('')
      setCases(await api<CaseData>('/api/cases'))
    } catch (reason) { setMessage(`保存失败：${reason}`) }
  }

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-icon">雀</div><div><strong>雀魂助手</strong><small>REPLAY LAB / 0.3</small></div></div>
      <div className="side-section-title">工作台</div>
      <nav><a href="#overview" className="active"><span>◈</span> 项目概览</a><a href="#replay"><span>◷</span> 牌局回放</a><a href="#models"><span>▤</span> 模型实验</a><a href="#cases"><span>◇</span> 纠错案例</a></nav>
      <div className="sidebar-bottom"><div className="online-dot" /> 仅在本机运行<br /><small>真实牌局与修正保存在本地</small></div>
    </aside>
    <main>
      <header className="topbar"><span>雀魂麻将助手 / <b>复盘实验室</b></span><div className="topbar-right"><span className="pill">● LOCAL 127.0.0.1</span><span className="avatar">牛</span></div></header>
      {error && <div className="error-banner">{error}</div>}
      <div className="page-content">
        <section id="overview" className="hero"><div className="hero-copy"><div className="overline">AI MAHJONG WORKSPACE</div><h1>每一步判断，<br /><em>都有迹可循。</em></h1><p>从窗口画面到牌局事件，再到可检验的预测与赛后问答。当前模型实验与实战提示分开，未经独立验证的概率不会进入实时牌桌。</p><div className="hero-actions"><a href="#replay" className="button primary">查看牌局回放 <span>↗</span></a><a href="#models" className="button secondary">查看模型实验</a></div></div><div className="hero-art" aria-hidden="true"><div className="tile-art tile-a">東</div><div className="tile-art tile-b"><i /><i /><i /><i /><i /></div><div className="tile-art tile-c">發</div><div className="hero-orbit orbit-one"/><div className="hero-orbit orbit-two"/></div></section>
        <div className="stat-grid"><div className="stat"><span>牌局入口</span><strong>02</strong><small>实时窗口 · 视频回放</small></div><div className="stat"><span>麻将模式</span><strong>3P <b>/</b> 4P</strong><small>独立实验报告</small></div><div className="stat"><span>当前模型状态</span><strong className="status-text">实验中</strong><small>未通过真实对局验证</small></div><div className="stat"><span>云端调用</span><strong>¥ 0</strong><small>默认完全本地</small></div></div>
        <section id="replay" className="section"><div className="section-heading"><div><div className="overline">01 / REPLAY</div><h2>牌局回放</h2><p>选择一场牌局，沿事件时间线查看舍牌与识别缺口。</p></div><span className="heading-note">观察 ≠ 已确认事实</span></div>
          <div className="replay-layout"><div className="card session-card"><div className="card-heading"><h3>牌局列表</h3><span>{sessions.length} 场</span></div><div className="session-list">{sessions.map(session => <button key={session.id} onClick={() => setSelected(session.id)} className={`session-item ${session.id === selected ? 'selected' : ''}`}><span className="mode-mark">{session.mode ?? '?'}P</span><span className="session-info"><strong>{session.synthetic ? '合成演示牌局' : '本地牌局记录'}</strong><small>{session.event_count} 个事件 · {session.round_count} 局</small></span><span className="session-arrow">›</span></button>)}</div><div className="card-foot">合成牌局仅用于展示交互，不证明识牌或模型准确率。</div></div>
            <div className="card timeline-card"><div className="card-heading"><h3>事件时间线</h3><span>{chosen?.synthetic ? '合成样例' : '本地记录'} · {chosen?.mode ?? '?'} 人麻将</span></div><div className="timeline">{events.map(event => <button key={event.sequence} className={`event-row ${event.sequence === activeNumber ? 'selected' : ''} ${event.confidence === 'unknown' ? 'uncertain' : ''}`} onClick={() => { setEventNumber(event.sequence); setReply(null) }}><span className="event-index">{String(event.sequence).padStart(2, '0')}</span><span className="event-dot"/><span className="event-main"><strong>{labels[event.kind] ?? event.kind}</strong><small>{event.seat ? seats[event.seat] ?? event.seat : '牌局'} · 第 {event.round_index} 局</small></span>{event.tile && <span className="mahjong-tile">{tileName(event.tile)}</span>}<span className={`confidence ${event.confidence}`}>{event.confidence === 'unknown' ? '待核对' : event.confidence === 'candidate' ? '疑似' : event.confidence === 'confirmed' ? '确认' : '观察'}</span></button>)}</div></div>
            <div className="right-column"><div className="card focus-card"><div className="card-heading"><h3>当前事件</h3><span>#{activeNumber ?? '—'}</span></div>{current ? <><div className="focus-icon">{current.tile ? tileName(current.tile) : '◈'}</div><h3>{labels[current.kind] ?? current.kind}</h3><p>{current.seat ? seats[current.seat] ?? current.seat : '牌局'} · {current.source}</p><div className="divider"/><small>识别状态：{current.confidence}</small><small>{current.note || '此事件来自连续观察或人工确认。'}</small></> : <p>暂无事件。</p>}</div><div className="card coach-card"><div className="card-heading"><h3>本地复盘助手</h3><span className="tiny-badge">证据回答</span></div><p>围绕选中的事件提问。答案会引用事件编号，无法从公开信息确定的内容会明确说明。</p><div className="question-row"><input aria-label="复盘问题" value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={event => { if (event.key === 'Enter') ask() }} placeholder="例如：对手听牌了吗？"/><button onClick={ask}>提问 ↗</button></div>{reply && <div className="reply"><strong>复盘回答</strong><p>{reply.answer}</p><div className="evidence">依据：{reply.evidence.length ? reply.evidence.map(number => <button key={number} onClick={() => setEventNumber(number)}>事件 #{number}</button>) : '暂无'}</div><small>{reply.limitations}</small></div>}</div></div></div></section>
        <section id="models" className="section"><div className="section-heading"><div><div className="overline">02 / MODEL LAB</div><h2>模型实验</h2><p>训练、验证和测试按整场牌局分开。合成数据的分数只证明实验管线能运行。</p></div><span className="heading-note">无达标报告则不显示实时概率</span></div><div className="model-grid">{[3, 4].map(mode => { const report = metrics[String(mode)]; return <div className="card model-card" key={mode}><div className="model-title"><span className="mode-mark">{mode}P</span><div><h3>{mode === 3 ? '三人麻将' : '四人麻将'}</h3><small>{report?.sources?.synthetic_demo ? '合成数据实验' : '等待真实数据'}</small></div><span className={`badge ${report?.promoted ? 'good' : ''}`}>{report?.promoted ? '已验证' : '实验中'}</span></div><div className="model-stats"><div><span>测试牌局</span><strong>{report?.games?.test ?? '—'}</strong></div><div><span>听牌 Brier ↓</span><strong>{decimal(report?.tenpai?.model.brier)}</strong></div><div><span>等待召回@5 ↑</span><strong>{percentage(report?.waits?.model_recall_at_5)}</strong></div></div><div className="comparison"><span>听牌误差与规则基线</span><div className="bar-row"><small>模型</small><div><i style={{width: `${Math.min(100, (report?.tenpai?.model.brier ?? 0) * 300)}%`}}/></div><b>{decimal(report?.tenpai?.model.brier)}</b></div><div className="bar-row baseline"><small>规则</small><div><i style={{width: `${Math.min(100, (report?.tenpai?.rule_bucket_baseline.brier ?? 0) * 300)}%`}}/></div><b>{decimal(report?.tenpai?.rule_bucket_baseline.brier)}</b></div></div><div className="model-foot">{report?.reason ?? '尚无训练报告'}。校准误差 ECE：{decimal(report?.tenpai?.model.ece)}；荣和风险 Brier：{decimal(report?.ron?.model_brier)}；测试样本：{report?.samples?.test ?? '—'}。</div></div> })}</div></section>
        <section id="cases" className="section"><div className="section-heading"><div><div className="overline">03 / FEEDBACK LOOP</div><h2>纠错与改进</h2><p>人工修正保留原始事件，用来建立后续可审核的标注集。</p></div></div><div className="case-grid"><div className="card"><div className="card-heading"><h3>当前事件纠错</h3><span>人工标注</span></div><p className="case-description">发现牌名读错时，在这里留下正确牌名。修正不会自动训练模型，也不会覆盖原始观察。</p><div className="question-row"><input aria-label="正确牌名" value={correction} onChange={event => setCorrection(event.target.value)} placeholder="例如：5p" disabled={chosen?.synthetic}/><button onClick={correct} disabled={chosen?.synthetic || !current || !correction.trim()}>保存修正</button></div><small>{chosen?.synthetic ? '合成演示事件不能进入训练标注。请选一场真实牌局。' : message || '修正仅保存在本机。'}</small></div><div className="card"><div className="card-heading"><h3>待检查案例</h3><span>{cases.gaps.length + cases.corrections.length} 条</span></div><div className="case-list">{cases.corrections.slice(0, 3).map(item => <div key={`c-${item.id}`}><span>人工修正</span><strong>事件 #{item.sequence} → {item.corrected_value}</strong></div>)}{cases.gaps.slice(-3).reverse().map(item => <div key={`g-${item.session_id}-${item.sequence}`}><span>跟踪缺口</span><strong>{item.session_id.slice(0, 8)} · 事件 #{item.sequence}</strong></div>)}{cases.gaps.length + cases.corrections.length === 0 && <p>暂无真实牌局纠错案例。合成演示中的缺口不会计入这里。</p>}</div></div></div></section>
        <footer>雀魂麻将助手 · 本地研究项目 <span>数据留在本机 · 预测需经独立验证</span></footer>
      </div>
    </main>
  </div>
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)
