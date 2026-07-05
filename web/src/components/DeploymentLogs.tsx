"use client";

import { useEffect, useRef, useState } from "react";
import type { LogAction } from "@/lib/api";
import { deploymentWebSocketUrl } from "@/lib/api";

type Props = {
  deploymentId: string;
  initialActions?: LogAction[];
};

export function DeploymentLogs({ deploymentId, initialActions = [] }: Props) {
  const [logs, setLogs] = useState<LogAction[]>(initialActions);
  const [connected, setConnected] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setLogs(initialActions);
  }, [deploymentId, initialActions]);

  useEffect(() => {
    if (!deploymentId) return;

    const ws = new WebSocket(deploymentWebSocketUrl(deploymentId));
    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === "log") {
          setLogs((prev) => {
            const exists = prev.some(
              (item) =>
                item.actionTimestamp === payload.actionTimestamp &&
                item.action === payload.action,
            );
            if (exists) return prev;
            return [...prev, payload as LogAction];
          });
        }
      } catch {
        // ignore
      }
    };

    return () => ws.close();
  }, [deploymentId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div className="log-panel">
      <div className="log-header">
        <span className="log-title">What&apos;s happening</span>
        <span className="log-live">
          <span className={`log-live-dot ${connected ? "on" : ""}`} />
          {connected ? "Live" : "Connecting…"}
        </span>
      </div>
      <div className="log-body">
        {logs.length === 0 ? (
          <p className="log-empty">Hang tight — build logs will show up here…</p>
        ) : (
          logs.map((log) => (
            <div key={`${log.actionTimestamp}-${log.action}`} className="log-line">
              <span className="log-time">{formatTime(log.actionTimestamp)}</span>{" "}
              <span className="log-tag">{log.action}</span> {log.message}
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}
