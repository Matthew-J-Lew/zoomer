"use client";

import React, { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Presentation, Sparkles } from "lucide-react";

export default function MeetingPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [question, setQuestion] = useState("");

  // Read topic updates setting from URL params
  const topicUpdatesEnabled = searchParams.get("topicUpdates") !== "false";

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


        {/* Center Content: Meeting in Progress */}
        <div className="flex-1 flex flex-col items-center justify-center text-center max-w-4xl mx-auto pb-24">
          <div className="mb-6">
            <Presentation className="w-20 h-20 text-accent mx-auto" strokeWidth={1.5} />
          </div>
          <h1 className="text-3xl sm:text-4xl font-semibold text-primary-text leading-tight">
            Meeting in Progress
          </h1>
          <p className="mt-4 text-secondary-text text-lg max-w-lg">
            Your assistant is listening and will provide a summary when the meeting ends.
          </p>

          {/* Topic Box - only shown when topic updates are enabled */}
          {topicUpdatesEnabled && (
            <div className="mt-8">
              <div className="bg-surface border border-border rounded-2xl px-8 py-6 shadow-lg max-w-xl">
                <div className="flex items-center justify-center gap-2 mb-4">
                  <Sparkles className="w-4 h-4 text-accent" />
                  <h2 className="text-sm uppercase tracking-wider text-muted-text font-semibold">
                    Current Topic
                  </h2>
                </div>
                <p className="text-lg sm:text-xl font-medium text-primary-text leading-relaxed">
                  Weekly Sync with Design Team — Discussing the new maximizing user retention strategies and upcoming Q3 roadmap.
                </p>
              </div>
            </div>
          )}
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
