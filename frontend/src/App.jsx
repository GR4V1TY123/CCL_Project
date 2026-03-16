import { useEffect, useMemo, useState } from "react";
import {
  addKnowledge,
  addStudent,
  approveLog,
  clearToken,
  deleteLog,
  getChatHistory,
  getKnowledge,
  getLogs,
  getMe,
  getPlaybook,
  getStudents,
  login,
  markMessageInvalid,
  register,
  sendChatMessage,
} from "./api";
import "./App.css";

function ChatMessage({ message, isLastAssistant, onMarkInvalid }) {
  return (
    <div className={`message message-${message.role}`}>
      <div className="message-meta">
        <span className="message-role">{message.role}</span>
      </div>
      <div className="message-content">{message.content}</div>
      {isLastAssistant && (
        <button className="btn-small" onClick={onMarkInvalid}>
          Mark as invalid
        </button>
      )}
    </div>
  );
}

function ChatTab({ onError }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const lastAssistantIndex = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") return i;
    }
    return -1;
  }, [messages]);

  useEffect(() => {
    (async () => {
      try {
        const { messages } = await getChatHistory();
        setMessages(messages);
      } catch (err) {
        onError(err);
      }
    })();
  }, [onError]);

  const send = async (event) => {
    event.preventDefault();
    if (!input.trim()) return;

    setLoading(true);
    try {
      const res = await sendChatMessage(input.trim());
      setMessages(res.messages);
      setInput("");
    } catch (err) {
      onError(err);
    } finally {
      setLoading(false);
    }
  };

  const markInvalid = async () => {
    if (lastAssistantIndex < 0) return;
    setLoading(true);
    try {
      await markMessageInvalid(lastAssistantIndex);
      // optionally refresh logs by emitting a custom event
      window.dispatchEvent(new CustomEvent("ccl:logs-updated"));
    } catch (err) {
      onError(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="tab-content">
      <div className="chat-header">
        <h2>Student Information Chat</h2>
        <p className="subtitle">Ask about general info or your student data (use your secret key to unlock private info).</p>
      </div>
      <div className="chat-window" id="chat-window">
        {messages.length === 0 ? (
          <div className="empty-state">Start the conversation by asking a question.</div>
        ) : (
          messages.map((msg, idx) => (
            <ChatMessage
              key={idx}
              message={msg}
              isLastAssistant={idx === lastAssistantIndex}
              onMarkInvalid={markInvalid}
            />
          ))
        )}
      </div>

      <form className="chat-input" onSubmit={send}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your question..."
          disabled={loading}
          aria-label="Chat input"
        />
        <button type="submit" className="btn-primary" disabled={loading || !input.trim()}>
          {loading ? "Sending..." : "Send"}
        </button>
      </form>
    </div>
  );
}

function AdminTab({ onError }) {
  const [knowledge, setKnowledge] = useState([]);
  const [studentsCount, setStudentsCount] = useState(0);
  const [logs, setLogs] = useState([]);
  const [playbook, setPlaybook] = useState({ bullets: [] });
  const [newKnowledge, setNewKnowledge] = useState({ topic: "", info: "" });
  const [newStudent, setNewStudent] = useState({ name: "", secret_key: "", major: "", gpa: 3.0, enrollment_year: 2024 });
  const [pendingRule, setPendingRule] = useState({});

  const loadAll = async () => {
    try {
      const [kRes, sRes, pRes, lRes] = await Promise.all([
        getKnowledge(),
        getStudents(),
        getPlaybook(),
        getLogs(),
      ]);
      setKnowledge(kRes.learned_facts || []);
      setStudentsCount(sRes.students_count ?? 0);
      setPlaybook(pRes.playbook ?? { bullets: [] });
      setLogs(lRes.logs || []);
      setPendingRule({});
    } catch (err) {
      onError(err);
    }
  };

  useEffect(() => {
    loadAll();

    const handleLogsUpdated = () => {
      loadAll();
    };

    window.addEventListener("ccl:logs-updated", handleLogsUpdated);
    return () => window.removeEventListener("ccl:logs-updated", handleLogsUpdated);
  }, []);

  const handleAddKnowledge = async (event) => {
    event.preventDefault();
    if (!newKnowledge.topic.trim() || !newKnowledge.info.trim()) return;

    try {
      await addKnowledge(newKnowledge.topic.trim(), newKnowledge.info.trim());
      setNewKnowledge({ topic: "", info: "" });
      await loadAll();
    } catch (err) {
      onError(err);
    }
  };

  const handleAddStudent = async (event) => {
    event.preventDefault();
    const payload = {
      name: newStudent.name.trim(),
      secret_key: newStudent.secret_key.trim(),
      major: newStudent.major.trim(),
      gpa: Number(newStudent.gpa),
      enrollment_year: Number(newStudent.enrollment_year),
    };
    if (!payload.name || !payload.secret_key) return;

    try {
      await addStudent(payload);
      setNewStudent({ name: "", secret_key: "", major: "", gpa: 3.0, enrollment_year: 2024 });
      await loadAll();
    } catch (err) {
      onError(err);
    }
  };

  const handleApproveLog = async (log) => {
    const ruleText = pendingRule[log.id] || log.suggested_fix?.new_rule || "";
    if (!ruleText.trim()) return;

    try {
      await approveLog(log.id, ruleText.trim());
      await loadAll();
    } catch (err) {
      onError(err);
    }
  };

  const handleDeleteLog = async (logId) => {
    try {
      await deleteLog(logId);
      await loadAll();
    } catch (err) {
      onError(err);
    }
  };

  return (
    <div className="tab-content">
      <div className="admin-header">
        <h2>Admin Portal</h2>
        <p className="subtitle">Manage knowledge, student records, and safety logs.</p>
      </div>

      <section className="admin-grid">
        <div className="card">
          <h3>Add General Knowledge</h3>
          <form onSubmit={handleAddKnowledge} className="form-stack">
            <label>
              Topic / Keyword
              <input
                value={newKnowledge.topic}
                onChange={(e) => setNewKnowledge((v) => ({ ...v, topic: e.target.value }))}
                placeholder="e.g. admissions"
                required
              />
            </label>
            <label>
              Info
              <textarea
                value={newKnowledge.info}
                onChange={(e) => setNewKnowledge((v) => ({ ...v, info: e.target.value }))}
                placeholder="Add details for this topic..."
                required
              />
            </label>
            <button type="submit" className="btn-primary">
              Add Info
            </button>
          </form>

          <h4>Learned Facts</h4>
          {knowledge.length === 0 ? (
            <p className="note">No learned facts yet.</p>
          ) : (
            <ul className="list">
              {knowledge.map((fact, idx) => (
                <li key={idx}>{fact}</li>
              ))}
            </ul>
          )}
        </div>

        <div className="card">
          <h3>Student Records</h3>
          <form onSubmit={handleAddStudent} className="form-stack">
            <label>
              Student Name
              <input
                value={newStudent.name}
                onChange={(e) => setNewStudent((v) => ({ ...v, name: e.target.value }))}
                placeholder="Full name"
                required
              />
            </label>
            <label>
              Secret Key
              <input
                value={newStudent.secret_key}
                onChange={(e) => setNewStudent((v) => ({ ...v, secret_key: e.target.value }))}
                placeholder="SEC123"
                required
              />
            </label>
            <label>
              Major
              <input
                value={newStudent.major}
                onChange={(e) => setNewStudent((v) => ({ ...v, major: e.target.value }))}
                placeholder="Computer Science"
              />
            </label>
            <div className="grid-2">
              <label>
                GPA
                <input
                  type="number"
                  min={0}
                  max={4}
                  step={0.1}
                  value={newStudent.gpa}
                  onChange={(e) => setNewStudent((v) => ({ ...v, gpa: Number(e.target.value) }))}
                />
              </label>
              <label>
                Enrollment Year
                <input
                  type="number"
                  value={newStudent.enrollment_year}
                  onChange={(e) => setNewStudent((v) => ({ ...v, enrollment_year: Number(e.target.value) }))}
                />
              </label>
            </div>
            <button type="submit" className="btn-primary">
              Add Student
            </button>
          </form>
          <p className="note">Total students in DB: {studentsCount}</p>
        </div>

        <div className="card card-full">
          <h3>Playbook Rules & Safety Logs</h3>
          <div className="playbook">
            <h4>Current Rules</h4>
            <ul className="list">
              {playbook.bullets?.map((b) => (
                <li key={b.id}>{b.rule}</li>
              ))}
            </ul>
          </div>

          <h4>Reported Issues</h4>
          {logs.length === 0 ? (
            <p className="note">No reported issues currently in the queue.</p>
          ) : (
            logs.map((log) => (
              <div key={log.id} className="log-card">
                <div className="log-header">
                  <strong>Query:</strong> {log.query}
                </div>
                <p>
                  <strong>Bot Response:</strong> {log.response}
                </p>
                {log.suggested_fix && (
                  <div className="suggestion">
                    <strong>Suggested Rule:</strong>
                    <textarea
                      value={pendingRule[log.id] ?? log.suggested_fix.new_rule}
                      onChange={(e) =>
                        setPendingRule((prev) => ({ ...prev, [log.id]: e.target.value }))
                      }
                      rows={3}
                    />
                  </div>
                )}
                <div className="button-row">
                  <button className="btn-secondary" onClick={() => handleApproveLog(log)}>
                    Approve Fix
                  </button>
                  <button className="btn-secondary" onClick={() => handleDeleteLog(log.id)}>
                    Delete Log
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}

function AuthScreen({ onAuth, onError }) {
  const [mode, setMode] = useState("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!username.trim() || !password.trim()) return;

    setLoading(true);
    try {
      await (mode === "login"
        ? login(username.trim(), password.trim())
        : register(username.trim(), password.trim()));

      onAuth();
    } catch (err) {
      onError(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <h2>{mode === "login" ? "Log in" : "Create an account"}</h2>
        <form onSubmit={handleSubmit} className="form-stack">
          <label>
            Username
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="your username"
              required
              autoFocus
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="your password"
              required
            />
          </label>
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? "Working..." : mode === "login" ? "Log in" : "Register"}
          </button>
        </form>

        <div className="auth-switch">
          {mode === "login" ? (
            <>
              <span>New here?</span>
              <button className="btn-link" onClick={() => setMode("register")}>Create an account</button>
            </>
          ) : (
            <>
              <span>Already have an account?</span>
              <button className="btn-link" onClick={() => setMode("login")}>Log in</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function App() {
  const [activeTab, setActiveTab] = useState("chat");
  const [error, setError] = useState(null);
  const [user, setUser] = useState(null);
  const [initializing, setInitializing] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const response = await getMe();
        setUser(response);
      } catch (err) {
        clearToken();
      } finally {
        setInitializing(false);
      }
    })();
  }, []);

  const handleAuthSuccess = async () => {
    try {
      const me = await getMe();
      setUser(me);
      setError(null);
    } catch (err) {
      setError(err);
    }
  };

  const handleLogout = () => {
    clearToken();
    setUser(null);
  };

  if (initializing) {
    return (
      <div className="app">
        <main className="main">
          <div className="loading">Loading…</div>
        </main>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="app">
        <main className="main">
          {error && (
            <div className="toast">
              <strong>Error:</strong> {error.message}
              <button className="btn-clear" onClick={() => setError(null)}>
                ✕
              </button>
            </div>
          )}
          <AuthScreen onAuth={handleAuthSuccess} onError={setError} />
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-dot" />
          <span>Student Info Chat</span>
        </div>

        <nav className="tabs">
          <button
            className={activeTab === "chat" ? "tab active" : "tab"}
            onClick={() => setActiveTab("chat")}
          >
            Chat
          </button>
          <button
            className={activeTab === "admin" ? "tab active" : "tab"}
            onClick={() => setActiveTab("admin")}
          >
            Admin
          </button>
        </nav>

        <div className="user-info">
          <span className="user-name">Logged in as {user.username}</span>
          <button className="btn-clear" onClick={handleLogout}>
            Logout
          </button>
        </div>
      </header>

      <main className="main">
        {error && (
          <div className="toast">
            <strong>Error:</strong> {error.message}
            <button className="btn-clear" onClick={() => setError(null)}>
              ✕
            </button>
          </div>
        )}
        {activeTab === "chat" ? <ChatTab onError={setError} /> : <AdminTab onError={setError} />}
      </main>

      <footer className="footer">
        <span>
          Backend: <code>{window.location.origin}</code>
        </span>
      </footer>
    </div>
  );
}

export default App;
