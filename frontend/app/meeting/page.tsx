"use client";

import React, { useState, useRef, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Presentation, Sparkles, Loader2 } from "lucide-react";

// Backend API URL - defaults to localhost:8000 for local development
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ChatMessage {
  id: string;
  type: "question" | "answer";
  content: string;
  confidence?: number;
  timestamp: Date;
}

function MeetingPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [currentTopic, setCurrentTopic] = useState<string>("");
  const [botStatus, setBotStatus] = useState<string>("joining");
  const [isDisconnecting, setIsDisconnecting] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Read bot_id and topic updates setting from URL params
  const botId = searchParams.get("botId") || "";
  const topicUpdatesEnabled = searchParams.get("topicUpdates") !== "false";

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Poll for topic updates
  useEffect(() => {
    if (!botId || !topicUpdatesEnabled) return;

    const fetchTopic = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/meeting/${botId}/topic`);
        if (res.ok) {
          const data = await res.json();
          if (data.topic) {
            setCurrentTopic(data.topic);
          }
        }
      } catch (e) {
        // Silently fail - topic updates are non-critical
        console.error("Failed to fetch topic:", e);
      }
    };

    // Initial fetch
    fetchTopic();

    // Poll every 10 seconds
    const interval = setInterval(fetchTopic, 10000);
    return () => clearInterval(interval);
  }, [botId, topicUpdatesEnabled]);

  // Poll for bot status
  useEffect(() => {
    if (!botId) return;

    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/meeting/${botId}/status`);
        if (res.ok) {
          const data = await res.json();
          setBotStatus(data.status || "joining");
          
          // Auto-redirect when meeting ends
          if (data.status === "done") {
            router.push(`/post-meeting?botId=${botId}`);
          }
        }
      } catch (e) {
        console.error("Failed to fetch status:", e);
      }
    };

    // Initial fetch
    fetchStatus();

    // Poll every 5 seconds
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [botId, router]);

  const handleEndMeeting = () => {
    router.push("/post-meeting");
  };

  const handleDisconnectClick = () => {
    setShowConfirmModal(true);
  };

  const handleConfirmDisconnect = async () => {
    setIsDisconnecting(true);
    try {
      // Call the leave endpoint
      await fetch(`${API_BASE_URL}/meeting/${botId}/leave`, {
        method: "POST",
      });
    } catch (e) {
      console.error("Failed to disconnect:", e);
    }
    setShowConfirmModal(false);
    router.push(`/post-meeting?botId=${botId}`);
  };

  const handleAskQuestion = async () => {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || isLoading) return;

    // Clear any previous error
    setError(null);

    // Add user's question to chat
    const questionMessage: ChatMessage = {
      id: `q-${Date.now()}`,
      type: "question",
      content: trimmedQuestion,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, questionMessage]);
    setQuestion("");
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/qa`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          bot_id: botId,
          question: trimmedQuestion,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Request failed with status ${response.status}`);
      }

      const data = await response.json();

      // Add assistant's answer to chat
      const answerMessage: ChatMessage = {
        id: `a-${Date.now()}`,
        type: "answer",
        content: data.answer,
        confidence: data.confidence,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, answerMessage]);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to get response";
      setError(errorMessage);
      // Remove the question if we failed to get an answer
      setMessages((prev) => prev.filter((m) => m.id !== questionMessage.id));
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAskQuestion();
    }
  };

  return (
    <div className="min-h-screen flex bg-background h-screen overflow-hidden relative">
      {/* Confirmation Modal */}
      {showConfirmModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-surface border border-border rounded-2xl p-6 shadow-2xl max-w-sm w-full mx-4 animate-in fade-in zoom-in-95 duration-200">
            <h3 className="text-lg font-semibold text-primary-text mb-2">Disconnect Bot?</h3>
            <p className="text-secondary-text text-sm mb-6">
              This will end the recording and take you to the meeting summary. Are you sure?
            </p>
            <div className="flex gap-3">
              <Button 
                variant="secondary" 
                className="flex-1" 
                onClick={() => setShowConfirmModal(false)}
              >
                Cancel
              </Button>
              <button 
                onClick={handleConfirmDisconnect}
                disabled={isDisconnecting}
                className="flex-1 px-4 py-2.5 rounded-xl bg-error text-white font-medium text-sm hover:bg-error/90 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {isDisconnecting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Disconnecting...
                  </>
                ) : (
                  "Disconnect"
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="flex-1 flex flex-col p-6 transition-all duration-300 ease-in-out">
        {/* Header / Status */}
        <header className="flex justify-between items-center mb-8">
          <div className="flex items-center gap-3">
             <div className={`flex items-center gap-3 bg-surface border border-border px-4 py-2 rounded-full shadow-sm`}>
                <div className={`w-2.5 h-2.5 rounded-full ${
                  botStatus === "in_call" 
                    ? "bg-success animate-pulse shadow-[0_0_8px_var(--color-success)]" 
                    : botStatus === "joining" 
                    ? "bg-warning animate-pulse shadow-[0_0_8px_var(--color-warning)]" 
                    : botStatus === "error" 
                    ? "bg-error" 
                    : "bg-muted"
                }`}></div>
                <span className={`text-sm font-medium ${
                  botStatus === "in_call" 
                    ? "text-success" 
                    : botStatus === "joining" 
                    ? "text-warning" 
                    : botStatus === "error" 
                    ? "text-error" 
                    : "text-muted-text"
                }`}>
                  {botStatus === "in_call" && "Connected"}
                  {botStatus === "joining" && "Connecting..."}
                  {botStatus === "error" && "Connection Error"}
                  {botStatus === "done" && "Meeting Ended"}
                </span>
             </div>
          </div>
          
          {/* Disconnect Button - Top Right */}
          <button 
            onClick={handleDisconnectClick}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-error/15 border-2 border-error text-error font-semibold text-sm hover:bg-error hover:text-white transition-all duration-200 shadow-lg hover:shadow-error/25"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Disconnect Bot
          </button>
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
                  {currentTopic || (
                    <span className="text-muted-text italic">Listening for topic updates...</span>
                  )}
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
          
          {/* Chat Messages Area */}
          <div className="flex-1 overflow-y-auto mb-4 space-y-3">
            {messages.length === 0 ? (
              <div className="text-center flex flex-col justify-center h-full text-muted-text text-sm">
                <p>No questions asked yet.</p>
                <p>Type below to ask the assistant.</p>
              </div>
            ) : (
              <>
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`rounded-xl px-4 py-3 text-sm ${
                      msg.type === "question"
                        ? "bg-accent/10 text-primary-text ml-4"
                        : "bg-surface-subtle text-secondary-text mr-4"
                    }`}
                  >
                    <p className="text-xs font-medium text-muted-text mb-1">
                      {msg.type === "question" ? "You" : "Assistant"}
                    </p>
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                    {msg.type === "answer" && msg.confidence !== undefined && (
                      <p className="text-xs text-muted-text mt-2">
                        Confidence: {Math.round(msg.confidence * 100)}%
                      </p>
                    )}
                  </div>
                ))}
                {isLoading && (
                  <div className="bg-surface-subtle rounded-xl px-4 py-3 text-sm mr-4 flex items-center gap-2 text-muted-text">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Thinking...</span>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-3 px-3 py-2 bg-error/10 border border-error/20 rounded-lg text-error text-xs">
              {error}
            </div>
          )}
          
          <div className="mt-auto">
             <textarea
                rows={3}
                placeholder="Ask about the meeting..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
                className="w-full px-4 py-3 rounded-xl border border-border bg-surface-subtle text-primary-text placeholder-muted-text focus:outline-none focus:ring-2 focus:ring-focus transition-shadow resize-none text-sm disabled:opacity-50"
              />
              <Button 
                className="w-full mt-3" 
                onClick={handleAskQuestion}
                disabled={isLoading || !question.trim()}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    Asking...
                  </>
                ) : (
                  "Ask"
                )}
              </Button>
          </div>
        </div>
      </aside>
    </div>
  );
}

export default function MeetingPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="w-8 h-8 animate-spin text-accent" />
      </div>
    }>
      <MeetingPageContent />
    </Suspense>
  );
}
