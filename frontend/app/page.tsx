"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";

export default function Home() {
  const router = useRouter();
  const [meetingLink, setMeetingLink] = useState("");
  const [topic, setTopic] = useState("");
  const [topicUpdatesEnabled, setTopicUpdatesEnabled] = useState(true);
  const [updateInterval, setUpdateInterval] = useState(60);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const formatInterval = (seconds: number) => {
    if (seconds < 60) return `${seconds} seconds`;
    const minutes = seconds / 60;
    return minutes === 1 ? "1 minute" : `${minutes} minutes`;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const backendBase = (process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000").replace(/\/$/, "");

      const resp = await fetch(`${backendBase}/start-meeting-bot`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          meeting_url: meetingLink,
          agenda: topic || undefined,
        }),
      });

      if (!resp.ok) {
        let detail: any = null;
        try { detail = await resp.json(); } catch {}
        const msg =
          (detail && (detail.detail || detail.error || JSON.stringify(detail))) ||
          `Request failed (${resp.status})`;
        throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
      }

      const data: { bot_id: string } = await resp.json();

      const params = new URLSearchParams({
        botId: data.bot_id,
        meetingUrl: meetingLink,
        topicUpdates: topicUpdatesEnabled.toString(),
        interval: updateInterval.toString(),
      });

      router.push(`/meeting?${params.toString()}`);
    } catch (err: any) {
      setError(err?.message || "Failed to start the meeting bot.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-background">
      <main className="w-full max-w-lg">
        <div className="text-center mb-10">
          <h1 className="text-6xl font-bold text-primary-text mb-2 tracking-tight" style={{ fontFamily: "var(--font-quicksand)" }}>
            Zoomer
          </h1>
          <p className="text-secondary-text text-lg">Your accessible meeting assistant</p>
        </div>

        <Card>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label htmlFor="meeting-link" className="block text-sm font-medium text-primary-text mb-2">
                Meeting Link
              </label>
              <input
                id="meeting-link"
                type="url"
                placeholder="https://zoom.us/j/1234567890"
                value={meetingLink}
                onChange={(e) => setMeetingLink(e.target.value)}
                required
                className="w-full px-4 py-3 rounded-xl border border-border bg-surface-subtle text-primary-text placeholder-muted-text focus:outline-none focus:ring-2 focus:ring-focus transition-shadow"
              />
            </div>

            <div>
              <label htmlFor="topic" className="block text-sm font-medium text-primary-text mb-2">
                Meeting Topic / Context
              </label>
              <textarea
                id="topic"
                rows={3}
                placeholder="Demo, talk about anything..."
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border border-border bg-surface-subtle text-primary-text placeholder-muted-text focus:outline-none focus:ring-2 focus:ring-focus transition-shadow resize-none"
              />
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <label htmlFor="topic-updates" className="text-sm font-medium text-primary-text">
                  Real-time topic updates
                </label>
                <button
                  type="button"
                  id="topic-updates"
                  role="switch"
                  aria-checked={topicUpdatesEnabled}
                  onClick={() => setTopicUpdatesEnabled(!topicUpdatesEnabled)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-focus ${
                    topicUpdatesEnabled ? "bg-accent" : "bg-surface-subtle"
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                      topicUpdatesEnabled ? "translate-x-6" : "translate-x-1"
                    }`}
                  />
                </button>
              </div>

              {topicUpdatesEnabled && (
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <label htmlFor="update-interval" className="text-sm text-secondary-text">
                      Update interval
                    </label>
                    <span className="text-sm font-medium text-accent">{formatInterval(updateInterval)}</span>
                  </div>
                  <input
                    id="update-interval"
                    type="range"
                    min="30"
                    max="300"
                    step="30"
                    value={updateInterval}
                    onChange={(e) => setUpdateInterval(Number(e.target.value))}
                    className="w-full h-2 bg-surface-subtle rounded-lg appearance-none cursor-pointer accent-accent"
                  />
                  <div className="flex justify-between text-xs text-muted-text">
                    <span>30s</span>
                    <span>5m</span>
                  </div>
                </div>
              )}
            </div>

            {error && (
              <div role="alert" className="rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-primary-text">
                {error}
              </div>
            )}

            <Button type="submit" className="w-full justify-center" disabled={isSubmitting}>
              {isSubmitting ? "Connecting..." : "Connect Assistant"}
            </Button>
          </form>
        </Card>
      </main>
    </div>
  );
}
