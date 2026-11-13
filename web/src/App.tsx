import { useEffect, useMemo, useState } from 'react'
import { ask, sampleQuestions } from './api'
import DrawingViewer from './DrawingViewer'
import type { AskResponse, DatasetQuestion, Role, Source } from './types'

const SOURCES = ['', 'cubicasa5k', 'swiss_dwellings', 'ifc_models', 'ifc_bench', 'opening_design']

export default function App() {
  const [question, setQuestion] = useState('')
  const [path, setPath] = useState('')
  const [role, setRole] = useState<Role>('')
  const [samples, setSamples] = useState<DatasetQuestion[]>([])
  const [source, setSource] = useState('cubicasa5k')
  const [expected, setExpected] = useState<DatasetQuestion | null>(null)
  const [res, setRes] = useState<AskResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const [selected, setSelected] = useState<number | null>(null)

  useEffect(() => {
    sampleQuestions(source || undefined).then(setSamples)
  }, [source])

  // boxes that belong to the drawing currently on screen
  const sources: Source[] = useMemo(
    () => (res?.evidence ?? []).flatMap((e) => e.sources ?? []).filter((s) => s.file === path),
    [res, path],
  )
  const page = sources[0]?.page ?? 1
  const warnings = (res?.evidence ?? []).flatMap((e) => e.warnings ?? [])
  const isIfc = path.toLowerCase().endsWith('.ifc')

  function pick(q: DatasetQuestion) {
    setQuestion(q.question)
    setPath(q.path)
    setExpected(q)
    setRes(null)
    setSelected(null)
  }

  async function submit() {
    if (!question.trim()) return
    setBusy(true)
    setErr('')
    setRes(null)
    setSelected(null)
    try {
      setRes(await ask(question, path, role))
    } catch (e) {
      setErr(String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="app">
      <aside className="panel">
        <h1>Trace</h1>
        <p className="sub">Ask a drawing anything. Every answer shows where it came from.</p>

        <label>
          题库样例
          <div className="row">
            <select value={source} onChange={(e) => setSource(e.target.value)}>
              {SOURCES.map((s) => (
                <option key={s} value={s}>{s || '全部来源'}</option>
              ))}
            </select>
            <select value="" onChange={(e) => pick(samples[Number(e.target.value)])}>
              <option value="">选一道题…</option>
              {samples.map((q, i) => (
                <option key={i} value={i}>{q.question.slice(0, 70)}</option>
              ))}
            </select>
          </div>
        </label>

        <label>
          图纸 / 模型路径
          <input value={path} onChange={(e) => setPath(e.target.value)} placeholder="data/cubicasa5k/high_quality-108.png" />
        </label>

        <label>
          问题
          <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={3}
            onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) submit() }} />
        </label>

        <div className="row">
          <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
            <option value="">任何角色</option>
            <option value="architect">建筑师</option>
            <option value="electrician">电工</option>
          </select>
          <button className="primary" onClick={submit} disabled={busy}>{busy ? '思考中…' : '提问'}</button>
        </div>

        {err && <div className="error">{err}</div>}

        {res && (
          <section className="answer">
            <p className="answer-text">{res.answer_text}</p>
            {expected && (
              <p className="expected">题库标准答案：{String(expected.answer)} {expected.unit ?? ''}</p>
            )}
            {warnings.length > 0 && (
              <ul className="warnings">{warnings.map((w, i) => <li key={i}>⚠ {w}</li>)}</ul>
            )}
            {sources.length > 0 && (
              <>
                <h3>证据（点击在图纸上定位）</h3>
                <ol className="evidence">
                  {sources.map((s, i) => (
                    <li key={i} className={i === selected ? 'on' : ''} onClick={() => setSelected(i)}>
                      {s.label ?? `#${i + 1}`} <span className="dim">p.{s.page}</span>
                    </li>
                  ))}
                </ol>
              </>
            )}
            <details>
              <summary>工具调用（{res.tool_calls.length}）</summary>
              <pre>{JSON.stringify(res.tool_calls, null, 2)}</pre>
            </details>
          </section>
        )}
      </aside>

      <main className="stage">
        {isIfc ? (
          <div className="viewer empty">IFC 3D 查看器待接入（That Open Engine，按 GUID 高亮）</div>
        ) : (
          <DrawingViewer path={path} page={page} sources={sources} selected={selected} onSelect={setSelected} />
        )}
      </main>
    </div>
  )
}
