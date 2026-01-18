"use client";
import React, { useState, useEffect } from "react";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";

export default function PostMeetingPage() {
  const [activeTab, setActiveTab] = useState<"transcript" | "summary" | "questions">("transcript");
  const [currentTime, setCurrentTime] = useState("00:00");
  const [language, setLanguage] = useState<"en" | "es">("en");
  const [translatedData, setTranslatedData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const INPUT_FILE = "transcript.final.jsonl"

useEffect(() => {
  const translateFile = async () => {
    if (!language) return;

    setLoading(true);

    try {
      const response = await fetch("http://localhost:8000/translate-file", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          filename: INPUT_FILE,
          target_lang: language,
        }),
      });

      if (!response.ok) {
        throw new Error(`Translation failed: ${response.statusText}`);
      }

      const data = await response.json();

      // Just log result (no download)
      console.log("Translated Data:", data.translated_data);
    } catch (err) {
      console.error("Translation Error:", err);
    } finally {
      setLoading(false);
    }
  };

  translateFile();
}, [language]);

  const mockTranscriptEn = [
    { time: "00:15", speaker: "Alex", text: "Okay, let's get started with the weekly sync." },
    { time: "00:22", speaker: "Sarah", text: "I have the updates on the user retention strategies." },
    { time: "00:45", speaker: "Alex", text: "Great, please go ahead." },
    { time: "01:10", speaker: "Sarah", text: "We've seen a 15% increase in engagement since the new feature rollout." },
    { time: "02:30", speaker: "Mike", text: "That's fantastic news. What about the Q3 roadmap?" },
  ];

  const mockTranscriptEs = [
    { time: "00:15", speaker: "Alex", text: "Bien, comencemos con la sincronización semanal." },
    { time: "00:22", speaker: "Sarah", text: "Tengo las actualizaciones sobre las estrategias de retención de usuarios." },
    { time: "00:45", speaker: "Alex", text: "Genial, por favor continúa." },
    { time: "01:10", speaker: "Sarah", text: "Hemos visto un aumento del 15% en la participación desde el lanzamiento de la nueva función." },
    { time: "02:30", speaker: "Mike", text: "Esa es una noticia fantástica. ¿Qué pasa con la hoja de ruta del Q3?" },
  ];

  const transcript = language === "en" ? mockTranscriptEn : mockTranscriptEs;

  const handleTranscriptClick = (time: string) => {
    setCurrentTime(time);
    // In a real app, this would seek the video player
  };

  return (
    <div className="min-h-screen bg-background p-6 flex flex-col h-screen overflow-hidden">
      <header className="mb-6 flex justify-between items-center">
        <div>
           <h1 className="text-2xl font-semibold text-primary-text">Meeting Recap</h1>
           <p className="text-secondary-text text-sm">Weekly Sync with Design Team • Oct 24, 2025</p>
        </div>
        <Button variant="secondary" onClick={() => window.print()}>Export Report</Button>
      </header>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-6 overflow-hidden">
        {/* Left Column: Recording Canvas */}
        <div className="lg:col-span-2 flex flex-col gap-4">
           <div className="bg-black rounded-2xl flex-1 flex items-center justify-center relative overflow-hidden shadow-sm group">
              {/* Mock Video Player */}
              <div className="absolute inset-0 bg-neutral-900 opacity-50"></div>
              <div className="text-center z-10">
                 <div className="w-16 h-16 rounded-full bg-white/20 backdrop-blur-md flex items-center justify-center mx-auto mb-4 cursor-pointer hover:bg-white/30 transition-all">
                    <svg className="w-8 h-8 text-white ml-1" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                 </div>
                 <p className="text-white font-medium text-lg">Watch Recording</p>
                 <p className="text-white/70 text-sm mt-1">{currentTime} / 45:00</p>
              </div>
           </div>
           
           <Card className="p-4 flex items-center justify-between">
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
        <Card className="flex flex-col h-full overflow-hidden p-0 relative">
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

           {activeTab === 'transcript' && (
              <div className="px-6 pt-4 pb-0">
                 <div className="relative inline-block">
                    <svg className="w-4 h-4 text-secondary-text absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                       <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <select 
                       value={language}
                       onChange={(e) => setLanguage(e.target.value as "en" | "es")}
                       className="bg-surface-subtle border border-border text-secondary-text text-sm rounded-lg pl-9 pr-8 py-2 focus:outline-none focus:ring-2 focus:ring-focus cursor-pointer hover:border-accent-primary transition-colors appearance-none"
                       style={{ backgroundImage: `url("data:image/svg+xml,%3csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 20 20'%3e%3cpath stroke='%236b7280' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M6 8l4 4 4-4'/%3e%3c/svg%3e")`, backgroundPosition: "right 0.5rem center", backgroundRepeat: "no-repeat", backgroundSize: "1.5em 1.5em" }}
                     >
                       <option value="en">English</option>
                       <option value="es">Spanish</option>
                    </select>
                 </div>
              </div>
           )}
           
           <div className="flex-1 overflow-y-auto p-4 scrollbar-thin scrollbar-thumb-surface-subtle scrollbar-track-transparent">
              {activeTab === 'transcript' && (
                 <div className="space-y-1">

                    {transcript.map((item, index) => (
                       <div 
                         key={index} 
                         onClick={() => handleTranscriptClick(item.time)}
                         className="p-2 rounded-lg hover:bg-surface-subtle cursor-pointer transition-colors group"
                       >
                          <div className="flex justify-between items-baseline mb-1">
                             <span className="font-semibold text-sm text-primary-text">{item.speaker}</span>
                             <span className="text-xs text-muted-text font-mono group-hover:text-accent-primary transition-colors">{item.time}</span>
                          </div>
                          <p className="text-secondary-text text-sm leading-relaxed">{item.text}</p>
                       </div>
                    ))}
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
