import React from "react";
import ReidInterface from "@/components/ReidInterface";

export default function FridrHallPage() {
  return (
    <div className="min-h-screen bg-zinc-950 text-white selection:bg-emerald-500/30 flex flex-col items-center justify-center relative overflow-hidden">
      {/* Background Ambient Effects */}
      <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-emerald-900/20 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full bg-cyan-900/20 blur-[120px] pointer-events-none" />
      
      <div className="z-10 w-full max-w-5xl px-6 flex flex-col items-center">
        <div className="mb-12 text-center space-y-4">
          <h1 className="text-4xl md:text-5xl font-light tracking-widest text-emerald-50/90">
            FRIÐR HALL
          </h1>
          <p className="text-lg text-emerald-200/50 tracking-wider font-light">
            THE INNER CITADEL • MENTAL STABILIZATION
          </p>
        </div>

        <ReidInterface />
      </div>
    </div>
  );
}
