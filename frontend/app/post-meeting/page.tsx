"use client";

import React, { useState, useEffect, Suspense, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Loader2 } from "lucide-react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface TranscriptItem {
  ts: number;
  speaker: string;
  text: string;
}

function PostMeetingContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const botId = searchParams.get("botId") || "";
  const videoRef = useRef<HTMLVideoElement>(null);
  
  const [activeTab, setActiveTab] = useState<"transcript" | "summary" | "questions">("transcript");
  const [recordingUrl, setRecordingUrl] = useState<string>("");
  const [isLoadingRecording, setIsLoadingRecording] = useState(true);
  const [transcript, setTranscript] = useState<TranscriptItem[]>([]);
  const [recordingStartedAt, setRecordingStartedAt] = useState<number>(0);
  const [isLoadingTranscript, setIsLoadingTranscript] = useState(true);

  // Fetch recording URL
  useEffect(() => {
    if (!botId) {
      setIsLoadingRecording(false);
      return;
    }

    const fetchRecording = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/meeting/${botId}/status`);
        if (res.ok) {
          const data = await res.json();
          if (data.recording_url) {
            setRecordingUrl(data.recording_url);
            setIsLoadingRecording(false);
          }
        }
      } catch (e) {
        console.error("Failed to fetch recording:", e);
      }
    };

    fetchRecording();
    const interval = setInterval(() => {
      if (!recordingUrl) fetchRecording();
    }, 5000);
    const timeout = setTimeout(() => {
      setIsLoadingRecording(false);
      clearInterval(interval);
    }, 120000);

    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [botId, recordingUrl]);

  // Fetch transcript
  useEffect(() => {
    if (!botId) {
      setIsLoadingTranscript(false);
      return;
    }

    const fetchTranscript = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/meeting/${botId}/transcript`);
        if (res.ok) {
          const data = await res.json();
          setTranscript(data.transcript || []);
          setRecordingStartedAt(data.recording_started_at || 0);
        }
      } catch (e) {
        console.error("Failed to fetch transcript:", e);
      } finally {
        setIsLoadingTranscript(false);
      }
    };

    fetchTranscript();
  }, [botId]);

  // Format relative timestamp as MM:SS
  const formatTime = (ts: number): string => {
    if (recordingStartedAt === 0) return "00:00";
    const relativeSeconds = Math.max(0, ts - recordingStartedAt);
    const minutes = Math.floor(relativeSeconds / 60);
    const seconds = Math.floor(relativeSeconds % 60);
    return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
  };

  // Calculate relative seconds for seeking
  const getRelativeSeconds = (ts: number): number => {
    if (recordingStartedAt === 0) return 0;
    return Math.max(0, ts - recordingStartedAt);
  };

  const handleTranscriptClick = (ts: number) => {
    const seconds = getRelativeSeconds(ts);
    if (videoRef.current) {
      videoRef.current.currentTime = seconds;
      videoRef.current.play();
    }
  };

  return (
    <div className="h-screen bg-background p-6 flex flex-col">
      <header className="mb-6 flex justify-between items-center">
        <div>
           <h1 className="text-2xl font-semibold text-primary-text">Meeting Recap</h1>
           <p className="text-secondary-text text-sm">Weekly Sync with Design Team • Oct 24, 2025</p>
        </div>
        <div className="flex gap-3">
          <Button variant="secondary" onClick={() => router.push("/")}>New Meeting</Button>
          <Button variant="secondary" onClick={() => window.print()}>Export Report</Button>
        </div>
      </header>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 min-h-0">
        {/* Left Column: Recording Canvas */}
        <div className="lg:col-span-2 flex flex-col gap-4 min-h-0">
           <div className="bg-black flex-1 min-h-0 flex items-center justify-center relative overflow-hidden shadow-sm group">
              {recordingUrl ? (
                <video 
                  ref={videoRef}
                  className="w-full h-full object-contain"
                  controls
                  src={recordingUrl}
                >
                  Your browser does not support the video tag.
                </video>
              ) : isLoadingRecording ? (
                <div className="text-center z-10">
                  <Loader2 className="w-12 h-12 text-white animate-spin mx-auto mb-4" />
                  <p className="text-white font-medium text-lg">Processing Recording...</p>
                  <p className="text-white/70 text-sm mt-1">This may take a few moments</p>
                </div>
              ) : (
                <div className="text-center z-10">
                  <div className="w-16 h-16 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center mx-auto mb-4">
                    <svg className="w-8 h-8 text-white/50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <p className="text-white/70 font-medium text-lg">Recording Not Available</p>
                  <p className="text-white/50 text-sm mt-1">The recording may still be processing</p>
                </div>
              )}
           </div>
           
           <Card className="p-4 flex items-center justify-between flex-shrink-0">
              <div className="flex items-center gap-4">
                 <div className="w-10 h-10 rounded-full bg-accent-soft flex items-center justify-center text-accent-primary font-bold">A</div>
                 <div>
                    <p className="text-sm font-semibold text-primary-text">Alex (Host)</p>
                    <p className="text-xs text-secondary-text">Product Manager</p>
                 </div>
              </div>
               <div className="flex items-center gap-4">
                 <div className="w-10 h-10 rounded-full bg-orange-100 flex items-center justify-center text-orange-600 font-bold">S</div>
                 <div>
                    <p className="text-sm font-semibold text-primary-text">Sarah</p>
                    <p className="text-xs text-secondary-text">Lead Designer</p>
                 </div>
              </div>
           </Card>
        </div>

        {/* Right Column: Tabs */}
        <Card className="flex flex-col min-h-0 overflow-hidden p-0 relative">
           <div className="flex border-b border-border pr-20">
              <button 
                onClick={() => setActiveTab("transcript")}
                className={`flex-1 py-3 text-sm font-medium transition-colors border-b-2 ${activeTab === 'transcript' ? 'border-accent-primary text-accent-primary' : 'border-transparent text-secondary-text hover:text-primary-text'}`}
              >
                Transcript
              </button>
              <button 
                onClick={() => setActiveTab("summary")}
                className={`flex-1 py-3 text-sm font-medium transition-colors border-b-2 ${activeTab === 'summary' ? 'border-accent-primary text-accent-primary' : 'border-transparent text-secondary-text hover:text-primary-text'}`}
              >
                Summary
              </button>
               <button 
                onClick={() => setActiveTab("questions")}
                className={`flex-1 py-3 text-sm font-medium transition-colors border-b-2 ${activeTab === 'questions' ? 'border-accent-primary text-accent-primary' : 'border-transparent text-secondary-text hover:text-primary-text'}`}
              >
                Questions
              </button>
           </div>

           <div className="flex-1 min-h-0 overflow-y-auto p-4 pb-8 scrollbar-thin scrollbar-thumb-surface-subtle scrollbar-track-transparent">
              {activeTab === 'transcript' && (
                 <div className="space-y-1">
                    {isLoadingTranscript ? (
                      <div className="flex items-center justify-center py-8">
                        <Loader2 className="w-6 h-6 animate-spin text-muted-text" />
                      </div>
                    ) : transcript.length === 0 ? (
                      <p className="text-muted-text text-sm text-center py-8">No transcript available</p>
                    ) : (
                      transcript.map((item, index) => (
                       <div 
                         key={index} 
                         onClick={() => handleTranscriptClick(item.ts)}
                         className="p-2 rounded-lg hover:bg-surface-subtle cursor-pointer transition-colors group"
                       >
                          <div className="flex justify-between items-baseline mb-1">
                             <span className="font-semibold text-sm text-primary-text">{item.speaker}</span>
                             <span className="text-xs text-muted-text font-mono group-hover:text-accent-primary transition-colors">{formatTime(item.ts)}</span>
                          </div>
                          <p className="text-secondary-text text-sm leading-relaxed">{item.text}</p>
                       </div>
                      ))
                    )}
                 </div>
              )}

              {activeTab === "summary" && (
                 <div className="space-y-6">
                    <section>
                       <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-text mb-2">Key Decisions</h3>
                       <ul className="list-disc pl-5 space-y-2 text-sm text-primary-text">
                          <li>Approved the new user retention strategy.</li>
                          <li>Scheduled Q3 roadmap review for next Tuesday.</li>
                       </ul>
                    </section>
                     <section>
                       <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-text mb-2">Action Items</h3>
                       <div className="space-y-2">
                          <div className="flex items-start gap-2">
                             <input type="checkbox" className="mt-1 rounded border-gray-300 text-accent-primary focus:ring-accent-primary" defaultChecked />
                             <span className="text-sm text-secondary-text line-through">Draft announcement email</span>
                          </div>
                           <div className="flex items-start gap-2">
                             <input type="checkbox" className="mt-1 rounded border-gray-300 text-accent-primary focus:ring-accent-primary" />
                             <span className="text-sm text-primary-text">Sarah to share design assets</span>
                          </div>
                       </div>
                    </section>
                     <Button variant="secondary" className="w-full text-xs mt-4">Download Full Summary (PDF)</Button>
                 </div>
              )}

              {activeTab === "questions" && (
                 <div className="flex flex-col h-full">
                    <div className="flex-1 overflow-y-auto mb-4 flex flex-col items-center justify-center text-muted-text text-sm">
                        <svg className="w-12 h-12 mb-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                           <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                        </svg>
                        <p className="mb-1">Have more questions about the meeting?</p>
                        <p className="text-xs text-secondary-text">Ask the assistant about specific details or decisions.</p>
                    </div>
                    <div>
                       <textarea
                          rows={3}
                          placeholder="Ask about the meeting transcript..."
                          className="w-full px-4 py-3 rounded-xl border border-border bg-surface-subtle text-primary-text placeholder-muted-text focus:outline-none focus:ring-2 focus:ring-focus transition-shadow resize-none text-sm mb-3"
                       />
                       <Button className="w-full justify-center">
                          Ask Question
                       </Button>
                    </div>
                 </div>
              )}
           </div>
        </Card>
      </div>
    </div>
  );
}

export default function PostMeetingPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="w-8 h-8 animate-spin text-accent" />
      </div>
    }>
      <PostMeetingContent />
    </Suspense>
  );
}
