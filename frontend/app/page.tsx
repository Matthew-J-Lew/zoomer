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
  const [updateInterval, setUpdateInterval] = useState(60); // Default 60 seconds

  // Format seconds to readable string
  const formatInterval = (seconds: number) => {
    if (seconds < 60) return `${seconds} seconds`;
    const minutes = seconds / 60;
    return minutes === 1 ? "1 minute" : `${minutes} minutes`;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const params = new URLSearchParams({
      topicUpdates: topicUpdatesEnabled.toString(),
      interval: updateInterval.toString(),
    });
    router.push(`/meeting?${params.toString()}`)
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 bg-background">
      <main className="w-full max-w-lg">
        <div className="text-center mb-10">
          <h1 className="text-6xl font-bold text-primary-text mb-2 tracking-tight" style={{ fontFamily: 'var(--font-quicksand)' }}>
            Zoomer
          </h1>
          <p className="text-secondary-text text-lg">
            Your accessible meeting assistant
          </p>
        </div>

        <Card>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label
                htmlFor="meeting-link"
                className="block text-sm font-medium text-primary-text mb-2"
              >
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
              <label
                htmlFor="topic"
                className="block text-sm font-medium text-primary-text mb-2"
              >
                Meeting Topic / Context
              </label>
              <textarea
                id="topic"
                rows={3}
                placeholder="Weekly sync with the design team..."
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border border-border bg-surface-subtle text-primary-text placeholder-muted-text focus:outline-none focus:ring-2 focus:ring-focus transition-shadow resize-none"
              />
            </div>

            {/* Topic Updates Toggle */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <label
                  htmlFor="topic-updates"
                  className="text-sm font-medium text-primary-text"
                >
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

              {/* Interval Slider - only shown when updates are enabled */}
              {topicUpdatesEnabled && (
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <label
                      htmlFor="update-interval"
                      className="text-sm text-secondary-text"
                    >
                      Update interval
                    </label>
                    <span className="text-sm font-medium text-accent">
                      {formatInterval(updateInterval)}
                    </span>
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

            <Button type="submit" className="w-full justify-center">
              Connect Assistant
            </Button>
          </form>
        </Card>
      </main>
    </div>
  );
}
