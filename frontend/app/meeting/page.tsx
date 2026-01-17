"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";

export default function MeetingPage() {
  const router = useRouter();
  const [question, setQuestion] = useState("");

  const handleEndMeeting = () => {
    router.push("/post-meeting");
  };

  return (
    <div className="min-h-screen flex bg-background h-screen overflow-hidden">
      {/* Main Content */}
      <main className="flex-1 flex flex-col p-6 transition-all duration-300 ease-in-out">
        {/* Header / Status */}
        <header className="flex justify-between items-center mb-8">
          <div className="flex items-center gap-3">
             <div className="flex items-center gap-3 bg-surface border border-border px-4 py-2 rounded-full shadow-sm">
                <div className="w-2.5 h-2.5 rounded-full bg-success animate-pulse shadow-[0_0_8px_var(--color-success)]"></div>
                <span className="text-sm font-medium text-success">
                  Connected
                </span>
             </div>
             
            <Button variant="secondary" onClick={handleEndMeeting} className="text-sm border-error text-error hover:bg-error/10">
              Disconnect Bot
            </Button>
          </div>
        </header>

        {/* Center Content: Topic */}
        <div className="flex-1 flex flex-col items-center justify-center text-center max-w-2xl mx-auto">
          <div className="mb-6 opacity-80">
            <svg
              className="w-16 h-16 text-accent-primary mx-auto mb-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
              />
            </svg>
          </div>
          <h2 className="text-sm uppercase tracking-wider text-muted-text font-semibold mb-3">
            Current Topic
          </h2>
          <h1 className="text-3xl sm:text-4xl font-semibold text-primary-text leading-tight">
            Weekly Sync with Design Team
          </h1>
          <p className="mt-4 text-secondary-text text-lg max-w-lg">
            Discussing the new maximizing user retention strategies and upcoming Q3 roadmap.
          </p>
        </div>
      </main>

      {/* Static Sidebar */}
      <aside className="w-80 h-full bg-surface border-l border-border shadow-xl z-10 flex flex-col flex-shrink-0">
        <div className="p-6 flex flex-col h-full">
          <h3 className="text-lg font-semibold text-primary-text mb-4">
            Ask Private Questions
          </h3>
          <div className="flex-1 overflow-y-auto mb-4 text-center flex flex-col justify-center text-muted-text text-sm">
            <p>No questions asked yet.</p>
            <p>Type below to ask the assistant.</p>
          </div>
          
          <div className="mt-auto">
             <textarea
                rows={3}
                placeholder="Ask about the meeting..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border border-border bg-surface-subtle text-primary-text placeholder-muted-text focus:outline-none focus:ring-2 focus:ring-focus transition-shadow resize-none text-sm"
              />
              <Button className="w-full mt-3">
                Ask
              </Button>
          </div>
        </div>
      </aside>
    </div>
  );
}
