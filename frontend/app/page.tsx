"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";

export default function Home() {
  const router = useRouter();
  const [meetingLink, setMeetingLink] = useState("");
  const [topic, setTopic] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Simulate connection logic or navigation
    console.log("Connecting to:", meetingLink, "Topic:", topic);
    router.push("/meeting");
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

            <Button type="submit" className="w-full justify-center">
              Connect Assistant
            </Button>
          </form>
        </Card>
      </main>
    </div>
  );
}
