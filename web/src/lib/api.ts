export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3001/dev";

export const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:3001/dev";

export type Project = {
  projectId: string;
  name: string;
  githubUrl: string;
  ownerId?: string;
  createdAt: string;
};

export type Deployment = {
  deploymentId: string;
  projectId: string;
  status: string;
  createdAt?: string;
  githubUrl?: string;
  actions?: LogAction[];
};

export type LogAction = {
  deploymentId: string;
  actionTimestamp: string;
  action: string;
  message: string;
};

export async function createProject(input: {
  name: string;
  githubUrl: string;
  ownerId?: string;
}): Promise<Project> {
  const res = await fetch(`${API_URL}/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error ?? "Failed to create project");
  }
  return res.json();
}

export async function createDeployment(input: {
  projectId: string;
  userId?: string;
}): Promise<Deployment> {
  const res = await fetch(`${API_URL}/deployments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error ?? "Failed to create deployment");
  }
  return res.json();
}

export async function getDeployment(deploymentId: string): Promise<Deployment> {
  const res = await fetch(`${API_URL}/deployments/${deploymentId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error ?? "Failed to fetch deployment");
  }
  return res.json();
}

export async function getUser(userId: string) {
  const res = await fetch(`${API_URL}/users/${userId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error ?? "Failed to fetch user");
  }
  return res.json();
}

export function deploymentWebSocketUrl(deploymentId: string): string {
  const base = WS_URL.replace(/\/$/, "");
  const separator = base.includes("?") ? "&" : "?";
  return `${base}${separator}deploymentId=${encodeURIComponent(deploymentId)}`;
}
