import { useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Copy, FileText, LoaderCircle, Plus, Send, Sparkles } from 'lucide-react'
import { createSession, getRuntimeInfo, sendChat } from './api'
import type { Artifact, ChatResponse, RuntimeInfo, Source } from './api'
import './App.css'

type Message = {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources: Source[]
}

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [artifact, setArtifact] = useState<Artifact | null>(null)
  const [draft, setDraft] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isStarting, setIsStarting] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const initialized = useRef(false)

  useEffect(() => {
    if (initialized.current) return
    initialized.current = true
    void startConversation(false)
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  async function startConversation(showLoading = true) {
    if (showLoading) setIsStarting(true)
    setError(null)
    setMessages([])
    setArtifact(null)
    setDraft('')

    try {
      const [session, runtimeInfo] = await Promise.all([createSession(), getRuntimeInfo()])
      setSessionId(session.id)
      setRuntime(runtimeInfo)
    } catch (conversationError) {
      setSessionId(null)
      setError(conversationError instanceof Error ? conversationError.message : 'Unable to start a conversation.')
    } finally {
      setIsStarting(false)
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const query = draft.trim()
    if (!query || !sessionId || isLoading || isStarting) return

    setDraft('')
    setError(null)
    setMessages((current) => [...current, { id: crypto.randomUUID(), role: 'user', content: query, sources: [] }])
    setIsLoading(true)

    try {
      const response: ChatResponse = await sendChat(sessionId, query)
      setMessages((current) => [
        ...current,
        { id: crypto.randomUUID(), role: 'assistant', content: response.answer, sources: response.sources },
      ])
      setArtifact(response.artifact)
    } catch (chatError) {
      setError(chatError instanceof Error ? chatError.message : 'The assistant could not answer right now.')
    } finally {
      setIsLoading(false)
    }
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <div className="brand-lockup">
          <div className="brand-mark"><Sparkles size={18} strokeWidth={2.5} /></div>
          <div>
            <p className="eyebrow">Lenny Growth Assistant</p>
            <p className="subhead">Grounded product thinking, one question at a time.</p>
          </div>
        </div>
        <div className="header-actions">
          <div className="provider-pill" title="Current backend language model">
            <span className="status-dot" />
            {runtime ? `${runtime.provider} · ${runtime.model}` : 'Connecting to model…'}
          </div>
          <button className="new-chat-button" type="button" onClick={() => void startConversation()} disabled={isStarting}>
            <Plus size={16} />
            New conversation
          </button>
        </div>
      </header>

      <div className="workspace">
        <section className="chat-panel" aria-label="Chat conversation">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Conversation</p>
              <h1>Ask better questions.</h1>
            </div>
            <span className="session-label">{isStarting ? 'Starting session' : 'Private session'}</span>
          </div>

          <div className="message-list" aria-live="polite">
            {messages.length === 0 && !isStarting && (
              <div className="chat-empty-state">
                <div className="empty-icon"><Sparkles size={20} /></div>
                <h2>What are you working through?</h2>
                <p>Ask about product, growth, leadership, or request a grounded artifact from the transcript library.</p>
                <div className="prompt-chips">
                  <button type="button" onClick={() => setDraft('What are practical ways to improve activation?')}>Improve activation</button>
                  <button type="button" onClick={() => setDraft('Create a product strategy document for an early-stage growth team')}>Create a strategy doc</button>
                </div>
              </div>
            )}
            {isStarting && <div className="starting-state"><LoaderCircle className="spin" size={18} /> Creating your session…</div>}
            {messages.map((message) => (
              <article className={`message-row ${message.role}`} key={message.id}>
                <div className="message-avatar">{message.role === 'assistant' ? <Sparkles size={15} /> : 'Y'}</div>
                <div className="message-body">
                  <div className="message-meta">{message.role === 'assistant' ? 'Lenny Assistant' : 'You'}</div>
                  <div className="message-content">
                    {message.role === 'assistant' ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown> : <p>{message.content}</p>}
                  </div>
                  {message.role === 'assistant' && <Sources sources={message.sources} />}
                </div>
              </article>
            ))}
            {isLoading && <div className="message-row assistant"><div className="message-avatar"><Sparkles size={15} /></div><div className="message-body"><div className="message-meta">Lenny Assistant</div><div className="typing-indicator"><span /><span /><span /></div></div></div>}
            <div ref={messagesEndRef} />
          </div>

          {error && <div className="error-banner" role="alert">{error}</div>}
          <form className="composer" onSubmit={handleSubmit}>
            <textarea value={draft} onChange={(event) => setDraft(event.target.value)} onKeyDown={handleComposerKeyDown} placeholder="Ask a product or growth question…" rows={2} disabled={isStarting || isLoading || !sessionId} aria-label="Message" />
            <div className="composer-footer">
              <span>Enter to send · Shift + Enter for a new line</span>
              <button className="send-button" type="submit" disabled={!draft.trim() || isStarting || isLoading || !sessionId} aria-label="Send message"><Send size={17} /></button>
            </div>
          </form>
        </section>

        <ArtifactViewer key={artifact ? `${artifact.title}-${artifact.content}` : 'empty'} artifact={artifact} />
      </div>
    </main>
  )
}

function Sources({ sources }: { sources: Source[] }) {
  if (!sources.length) return null
  return <div className="sources"><span>Sources</span>{sources.map((source) => <a href={safeUrl(source.source_url) ?? undefined} target="_blank" rel="noreferrer" key={`${source.episode_title}-${source.source_url}`}>{source.episode_title}{source.guest_name ? ` · ${source.guest_name}` : ''}</a>)}</div>
}

function ArtifactViewer({ artifact }: { artifact: Artifact | null }) {
  const [showSource, setShowSource] = useState(false)
  const [copied, setCopied] = useState(false)

  async function copyArtifact() {
    if (!artifact) return
    await navigator.clipboard.writeText(artifact.content)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return <aside className="artifact-panel" aria-label="Artifact viewer">
    <div className="artifact-heading"><div><p className="section-kicker">Workspace</p><h2>Artifact viewer</h2></div>{artifact && <FileText size={19} />}</div>
    {!artifact ? <div className="artifact-empty"><div className="artifact-outline"><FileText size={22} /></div><p>Artifacts generated from your conversation will appear here.</p><span>Ask for a Markdown document or an HTML landing page to get started.</span></div> : <div className="artifact-content">
      <div className="artifact-title-row"><div><span className="artifact-type">{artifact.artifact_type === 'html' ? 'HTML' : 'MARKDOWN'} ARTIFACT</span><h3>{artifact.title}</h3></div><button className="icon-button" type="button" onClick={() => void copyArtifact()} title="Copy artifact"><Copy size={16} /> <span>{copied ? 'Copied' : 'Copy'}</span></button></div>
      <div className="artifact-toolbar"><span>{artifact.artifact_type === 'html' ? 'HTML Preview · Sandboxed' : 'Rendered Markdown'}</span><button type="button" onClick={() => setShowSource((value) => !value)}>{showSource ? 'Show preview' : 'Show source'}</button></div>
      <div className={`artifact-frame ${showSource ? 'source-view' : ''}`}>
        {showSource ? <pre>{artifact.content}</pre> : artifact.artifact_type === 'html' ? <iframe title="Sandboxed generated HTML" sandbox="" srcDoc={artifact.content} /> : <div className="markdown-preview"><ReactMarkdown remarkPlugins={[remarkGfm]}>{artifact.content}</ReactMarkdown></div>}
      </div>
      <div className="artifact-sources"><Sources sources={artifact.sources} /></div>
    </div>}
  </aside>
}

function safeUrl(value: string | null) {
  if (!value) return null
  try {
    const url = new URL(value)
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : null
  } catch {
    return null
  }
}

export default App
