import { useEffect, useState } from "react";

const API = "http://localhost:8000";
const EVENT_ID = 1;

type User = {
  id: number;
  email: string;
  role: string;
};

type Project = {
  id: number;
  name: string;
  description: string | null;
  track_id: number | null;
  repository_url: string | null;
  demo_url: string | null;
  submitted_at: string | null;
};

type Comment = {
  comment_id: number;
  author_id: number;
  content: string;
  created_at: string;
};

function App() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [token, setToken] = useState(
    localStorage.getItem("forgejudge_token") || ""
  );

  const [user, setUser] = useState<User | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [comments, setComments] = useState<Record<number, Comment[]>>({});
  const [commentText, setCommentText] = useState<Record<number, string>>({});

  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function api(
    path: string,
    options: RequestInit = {}
  ) {
    const headers = new Headers(options.headers);

    if (options.body) {
      headers.set("Content-Type", "application/json");
    }

    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    const response = await fetch(`${API}${path}`, {
      ...options,
      headers,
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "Request failed");
    }

    return data;
  }

  async function login() {
    try {
      setLoading(true);
      setMessage("");

      const body = new URLSearchParams();
      body.append("username", email);
      body.append("password", password);

      const response = await fetch(`${API}/api/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Login failed");
      }

      localStorage.setItem("forgejudge_token", data.access_token);
      setToken(data.access_token);
      setUser(data.user);
      setPassword("");
      setMessage(`Logged in as ${data.user.role}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    localStorage.removeItem("forgejudge_token");
    setToken("");
    setUser(null);
    setMessage("Logged out");
  }

  async function loadUser() {
    if (!token) {
      return;
    }

    try {
      const data = await api("/api/auth/me");
      setUser(data);
    } catch {
      logout();
    }
  }

  async function loadProjects() {
    try {
      setLoading(true);
      const data = await api(`/api/votes/event/${EVENT_ID}/projects`);
      setProjects(data);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Could not load projects"
      );
    } finally {
      setLoading(false);
    }
  }

  async function loadComments(projectId: number) {
    try {
      const data = await api(
        `/api/votes/${EVENT_ID}/${projectId}/comments`
      );

      setComments((current) => ({
        ...current,
        [projectId]: data,
      }));
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Could not load comments"
      );
    }
  }

  async function vote(projectId: number) {
    try {
      await api(`/api/votes/${EVENT_ID}/${projectId}`, {
        method: "POST",
      });

      setMessage("Vote submitted successfully.");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Vote failed"
      );
    }
  }

  async function addComment(projectId: number) {
    const content = (commentText[projectId] || "").trim();

    if (!content) {
      setMessage("Comment cannot be empty.");
      return;
    }

    try {
      await api(`/api/votes/${EVENT_ID}/${projectId}/comments`, {
        method: "POST",
        body: JSON.stringify({ content }),
      });

      setCommentText((current) => ({
        ...current,
        [projectId]: "",
      }));

      await loadComments(projectId);
      setMessage("Comment added.");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Could not add comment"
      );
    }
  }

  useEffect(() => {
    loadUser();
    loadProjects();
  }, []);

  useEffect(() => {
    projects.forEach((project) => {
      loadComments(project.id);
    });
  }, [projects]);

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>ForgeJudge</h1>
          <p>Trust the Result.</p>
        </div>

        <div className="user-area">
          {user ? (
            <>
              <span>
                {user.email} · {user.role}
              </span>
              <button onClick={logout}>Logout</button>
            </>
          ) : (
            <span>Not logged in</span>
          )}
        </div>
      </header>

      <section className="hero">
        <h2>Community Gallery</h2>
        <p>
          Projects are presented in randomized order for community
          voting.
        </p>

        {!user && (
          <div className="login-box">
            <h3>Login to vote or comment</h3>

            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />

            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />

            <button onClick={login} disabled={loading}>
              {loading ? "Logging in..." : "Login"}
            </button>
          </div>
        )}

        {message && <div className="message">{message}</div>}

        <button onClick={loadProjects} disabled={loading}>
          Refresh randomized gallery
        </button>
      </section>

      <section className="project-grid">
        {projects.map((project) => (
          <article className="project-card" key={project.id}>
            <div className="project-header">
              <span>Project #{project.id}</span>
              <span>Track {project.track_id ?? "—"}</span>
            </div>

            <h3>{project.name}</h3>

            <p>
              {project.description || "No description provided."}
            </p>

            <div className="project-links">
              {project.demo_url && (
                <a
                  href={project.demo_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Demo
                </a>
              )}

              {project.repository_url && (
                <a
                  href={project.repository_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Repository
                </a>
              )}
            </div>

            <div className="actions">
              <button
                disabled={!user}
                onClick={() => vote(project.id)}
              >
                Vote
              </button>
            </div>

            <div className="comments">
              <h4>Comments</h4>

              {(comments[project.id] || []).map((comment) => (
                <div className="comment" key={comment.comment_id}>
                  <strong>User {comment.author_id}</strong>
                  <p>{comment.content}</p>
                </div>
              ))}

              {user && (
                <div className="comment-box">
                  <textarea
                    placeholder="Write a comment..."
                    value={commentText[project.id] || ""}
                    onChange={(event) =>
                      setCommentText((current) => ({
                        ...current,
                        [project.id]: event.target.value,
                      }))
                    }
                  />

                  <button onClick={() => addComment(project.id)}>
                    Comment
                  </button>
                </div>
              )}
            </div>
          </article>
        ))}
      </section>
    </main>
  );
}

export default App;