"use client";

import { useState } from "react";
import type { Project } from "@/lib/api";
import { createProject } from "@/lib/api";
import { ProjectCard } from "@/components/ProjectCard";

export function Dashboard() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const project = await createProject({
        name,
        githubUrl,
        ownerId: "demo-user",
      });
      setProjects((prev) => [project, ...prev]);
      setName("");
      setGithubUrl("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't create that — try again?");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <section className="welcome">
        <div className="welcome-wave" aria-hidden="true">
          ✦
        </div>
        <h1 className="welcome-title">
          Got a repo? Let&apos;s get it live.
        </h1>
        <p className="welcome-desc">
          Paste a GitHub link, hit deploy, and watch your app come together.
          No config files, no fuss — just you and your code.
        </p>
      </section>

      <section className="section">
        <div className="card card-padded">
          <p className="card-label">Start here</p>
          <h2 className="card-heading">Add a project</h2>
          <p className="card-hint">
            Give it a name and drop in the repo URL. We&apos;ll handle the rest.
          </p>
          <form onSubmit={handleSubmit}>
            <div className="form-grid">
              <label className="field">
                <span className="field-label">What should we call it?</span>
                <input
                  className="field-input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  placeholder="my-cool-app"
                />
              </label>
              <label className="field">
                <span className="field-label">GitHub repo</span>
                <input
                  className="field-input"
                  value={githubUrl}
                  onChange={(e) => setGithubUrl(e.target.value)}
                  required
                  type="url"
                  placeholder="https://github.com/you/your-repo"
                />
              </label>
            </div>
            <div className="mt-md">
              <button type="submit" disabled={loading} className="btn btn-primary">
                {loading ? (
                  <>
                    <span className="spinner" />
                    Adding your project…
                  </>
                ) : (
                  "Add project"
                )}
              </button>
            </div>
          </form>
          {error && <div className="alert alert-error mt-md">{error}</div>}
        </div>
      </section>

      {projects.length > 0 && (
        <div className="divider">Your projects</div>
      )}

      <section className="section">
        {projects.length === 0 ? (
          <div className="empty-state">
            <div className="empty-emoji" aria-hidden="true">
              🌱
            </div>
            <p className="empty-title">Nothing here yet</p>
            <p className="empty-desc">
              Once you add a project, it&apos;ll show up right here.
              Your first deploy is just a few clicks away.
            </p>
          </div>
        ) : (
          <div>
            {projects.map((project) => (
              <ProjectCard key={project.projectId} project={project} />
            ))}
          </div>
        )}
      </section>
    </>
  );
}
