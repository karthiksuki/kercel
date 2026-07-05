"use client";

import { useState } from "react";
import type { Deployment, Project } from "@/lib/api";
import { createDeployment, getDeployment } from "@/lib/api";
import { DeploymentLogs } from "@/components/DeploymentLogs";
import { StatusBadge } from "@/components/StatusBadge";

type Props = {
  project: Project;
};

export function ProjectCard({ project }: Props) {
  const [deployment, setDeployment] = useState<Deployment | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleDeploy() {
    setLoading(true);
    setError(null);
    try {
      const created = await createDeployment({
        projectId: project.projectId,
        userId: project.ownerId,
      });
      setDeployment(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  async function refreshStatus() {
    if (!deployment) return;
    setLoading(true);
    setError(null);
    try {
      const latest = await getDeployment(deployment.deploymentId);
      setDeployment(latest);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't refresh");
    } finally {
      setLoading(false);
    }
  }

  return (
    <article className="card card-padded">
      <div className="stack-md">
        <div className="flex-between">
          <div style={{ flex: 1, minWidth: "180px" }}>
            <h2 className="project-name">{project.name}</h2>
            <p className="project-url">
              <GitHubIcon />
              {project.githubUrl.replace("https://github.com/", "")}
            </p>
          </div>
          <div className="flex-row">
            <button
              type="button"
              onClick={handleDeploy}
              disabled={loading}
              className="btn btn-primary"
            >
              {loading ? (
                <>
                  <span className="spinner" />
                  One sec…
                </>
              ) : (
                "Ship it"
              )}
            </button>
            {deployment && (
              <button
                type="button"
                onClick={refreshStatus}
                disabled={loading}
                className="btn btn-secondary"
              >
                Refresh
              </button>
            )}
          </div>
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        {deployment && (
          <div className="stack-sm">
            <div className="flex-row" style={{ flexWrap: "wrap" }}>
              <StatusBadge status={deployment.status} />
            </div>
            <DeploymentLogs
              deploymentId={deployment.deploymentId}
              initialActions={deployment.actions}
            />
          </div>
        )}
      </div>
    </article>
  );
}

function GitHubIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.395-.135-.345-.72-1.395-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
    </svg>
  );
}
