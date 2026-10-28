"use client";

import { useState, useEffect, useCallback } from "react";
import KnowledgeNoteComposer from "../../../components/KnowledgeNoteComposer";
import { motion } from "framer-motion";
import { apiFetch } from "../../../lib/desktopApi";

const errorMessage = (code) => ({
  library_vault_unavailable: "The configured Vault is unavailable. Check that its drive is connected, then retry.",
  library_database_missing: "The Library index is missing. Restore or rebuild the index, then retry.",
  library_database_unreadable: "The Library index cannot be opened. Check that the Vault is available, then retry.",
  library_schema_invalid: "The Library index has an unsupported or incomplete schema. Rebuild the index, then retry.",
  library_search_unavailable: "Library search is temporarily unavailable. Check the connection, then retry.",
}[code] || "Library data could not be loaded. Check the connection and retry.");

const safeError = (message) => Object.assign(new Error(message), { librarySafe: true });

const responseError = async (response) => {
  try {
    const payload = await response.json();
    return safeError(errorMessage(payload?.detail?.code || payload?.code));
  } catch {
    return safeError(errorMessage());
  }
};

const isDocument = (document) => document &&
  typeof document.id === "string" && typeof document.name === "string" &&
  typeof document.category === "string" &&
  (document.last_modified === null || typeof document.last_modified === "string" ||
    typeof document.last_modified === "number");

const formatModifiedDate = (value, options) => {
  const timestamp = typeof value === "number" ? value * 1000 : Date.parse(value);
  const date = new Date(timestamp);
  return Number.isNaN(date.getTime()) ? "Unknown date" : date.toLocaleDateString("en-US", options);
};

export default function LibraryDashboard({ onSelectEntity }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dashboardError, setDashboardError] = useState(null);
  
  // Search State
  const [searchQuery, setSearchQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const [searchRetry, setSearchRetry] = useState(0);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setDashboardError(null);
    try {
      const res = await apiFetch("/api/v1/library/dashboard");
      if (!res.ok) throw await responseError(res);
      const metrics = await res.json();
      if (!metrics || !Number.isFinite(metrics.total_documents) ||
          !Array.isArray(metrics.categories) || !metrics.categories.every((category) =>
            category && typeof category.name === "string" && Number.isFinite(category.count)) ||
          !Array.isArray(metrics.recent_documents) || !metrics.recent_documents.every(isDocument)) {
        throw safeError("The Library returned an unexpected dashboard response. Retry or contact support.");
      }
      setData(metrics);
    } catch (err) {
      setData(null);
      setDashboardError(err?.librarySafe ? err.message : "Library request failed. Check that the Vault is available and retry.");
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      setActiveCategory("");
      setActiveQuery(searchQuery.trim());
    }
  };

  const handleCategoryClick = (categoryName) => {
    setSearchQuery("");
    setActiveQuery("");
    setActiveCategory(categoryName);
  };

  const clearSearch = () => {
    setActiveQuery("");
    setActiveCategory("");
    setSearchQuery("");
    setSearchResults([]);
  };

  useEffect(() => {
    if (!activeQuery && !activeCategory) return;
    
    const fetchResults = async () => {
      setIsSearching(true);
      setSearchError(null);
      try {
        const params = new URLSearchParams();
        if (activeQuery) params.append("q", activeQuery);
        if (activeCategory) params.append("category", activeCategory);

        const res = await apiFetch(`/api/v1/library/search?${params.toString()}`);
        if (!res.ok) throw await responseError(res);
        const resultData = await res.json();
        if (!Array.isArray(resultData?.results) || !resultData.results.every(isDocument)) {
          throw safeError("Library search returned an unexpected response. Retry.");
        }
        setSearchResults(resultData.results);
      } catch (err) {
        setSearchResults([]);
        setSearchError(err?.librarySafe ? err.message : "Library search failed. Check the connection and retry.");
      } finally {
        setIsSearching(false);
      }
    };
    fetchResults();
  }, [activeQuery, activeCategory, searchRetry]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex flex-col justify-center items-center gap-4">
        <div className="w-16 h-16 border-4 border-emerald-500/30 border-t-emerald-400 rounded-full animate-spin shadow-[0_0_15px_rgba(52,211,153,0.5)]" />
        <div className="text-emerald-400 font-mono text-xs uppercase tracking-[0.3em] animate-pulse">
          Querying Zettelkasten...
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-zinc-950 flex flex-col justify-center items-center gap-4 px-6 text-center">
        <h1 className="text-2xl font-bold text-white">Library unavailable</h1>
        <KnowledgeNoteComposer />
        <p role="alert" className="max-w-xl text-zinc-300">{dashboardError || errorMessage()}</p>
        <button type="button" onClick={loadDashboard} className="rounded-lg border border-cyan-400/40 px-4 py-2 text-cyan-300 hover:bg-cyan-400/10">Retry</button>
      </div>
    );
  }

  return (
    <div className="h-full bg-zinc-950 text-white p-8 font-sans overflow-y-auto">
      <div className="max-w-6xl mx-auto space-y-12 pb-12">
        
        <KnowledgeNoteComposer candidates={activeQuery || activeCategory ? searchResults : data.recent_documents} />
        {/* Header Section */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col md:flex-row md:items-end justify-between gap-6 border-b border-white/10 pb-8"
        >
          <div>
            <h1 className="text-5xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-br from-emerald-300 via-teal-400 to-cyan-500 flex items-center gap-4 drop-shadow-[0_0_20px_rgba(52,211,153,0.3)]">
              <span>📚</span> Zettelkasten Nexus
            </h1>
            <p className="text-zinc-400 mt-2 font-mono uppercase tracking-widest text-sm">
              Vectorized Knowledge & Lore Repository
            </p>
          </div>
          <div className="flex flex-col gap-4 items-end min-w-[250px]">
            <div className="bg-zinc-900/60 border border-emerald-500/20 px-6 py-4 rounded-xl shadow-[0_0_15px_rgba(52,211,153,0.05)] backdrop-blur-md w-full">
              <div className="text-[10px] text-emerald-400 font-bold uppercase tracking-widest mb-1">Total Indexed</div>
              <div className="text-4xl font-black text-white">{data.total_documents.toLocaleString()} <span className="text-sm font-normal text-zinc-500">docs</span></div>
            </div>
            <form onSubmit={handleSearch} className="relative w-full shadow-[0_0_10px_rgba(34,211,238,0.05)]">
              <input 
                type="text" 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Deep Search..." 
                className="w-full bg-zinc-900/60 border border-white/10 focus:border-cyan-500/50 rounded-lg pl-4 pr-10 py-2 text-white font-mono text-sm outline-none transition-all placeholder:text-zinc-600"
              />
              <button type="submit" className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-cyan-400 transition-colors">
                🔍
              </button>
            </form>
          </div>
        </motion.div>

        {(activeQuery || activeCategory) ? (
          <div className="space-y-6">
            <div className="flex items-center gap-4">
              <button 
                onClick={clearSearch}
                className="text-zinc-500 hover:text-cyan-400 font-mono text-sm tracking-widest uppercase flex items-center gap-2 transition-colors"
              >
                <span>←</span> Back to Dashboard
              </button>
              <div className="h-4 w-px bg-white/20"></div>
              <div className="text-zinc-400 font-mono uppercase tracking-widest text-sm flex gap-4">
                {activeQuery && <span>Query: <span className="text-cyan-400">{activeQuery}</span></span>}
                {activeCategory && <span>Category: <span className="text-fuchsia-400">{activeCategory}</span></span>}
              </div>
            </div>

            {searchError ? (
              <div className="rounded-xl border border-amber-400/30 bg-amber-950/20 p-6 text-center text-amber-100" role="alert">
                <p>{searchError}</p>
                <button type="button" onClick={() => setSearchRetry((value) => value + 1)} className="mt-3 rounded-lg border border-amber-300/40 px-4 py-2 text-sm">Retry search</button>
              </div>
            ) : isSearching ? (
              <div className="flex flex-col justify-center items-center gap-4 py-20">
                <div className="w-12 h-12 border-4 border-cyan-500/30 border-t-cyan-400 rounded-full animate-spin shadow-[0_0_15px_rgba(34,211,238,0.5)]" />
                <div className="text-cyan-400 font-mono text-xs uppercase tracking-[0.3em] animate-pulse">
                  Scanning Vectors...
                </div>
              </div>
            ) : (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="space-y-4"
              >
                <div className="text-zinc-500 font-mono text-xs uppercase tracking-widest mb-4">
                  Found {searchResults.length} matches
                </div>
                
                {searchResults.length === 0 ? (
                  <div className="border border-dashed border-white/10 rounded-xl p-12 text-center text-zinc-500 font-mono uppercase tracking-widest">
                    No telemetry found matching parameters.
                  </div>
                ) : (
                  searchResults.map((doc, idx) => (
                    <div 
                      key={idx}
                      onClick={() => onSelectEntity && onSelectEntity({ id: doc.id, name: doc.name, type: 'file' })}
                      className="group bg-zinc-900/40 border border-white/5 hover:border-cyan-500/40 hover:bg-zinc-900 rounded-xl p-6 transition-all cursor-pointer shadow-sm hover:shadow-[0_0_15px_rgba(34,211,238,0.1)] flex flex-col gap-3"
                    >
                      <div className="flex justify-between items-start">
                        <div className="flex flex-col gap-1">
                          <span className="text-xs font-bold text-fuchsia-400 uppercase tracking-wider">
                            {doc.category}
                          </span>
                          <h3 className="text-lg font-bold text-white group-hover:text-cyan-300 transition-colors">
                            {doc.name}
                          </h3>
                        </div>
                        <div className="text-xs text-zinc-500 font-mono tracking-widest">
                          {formatModifiedDate(doc.last_modified, { month: 'short', day: 'numeric', year: 'numeric' })}
                        </div>
                      </div>
                      
                      <div className="text-sm text-zinc-400 leading-relaxed bg-black/20 p-3 rounded-lg border border-white/5 font-serif italic">
                        &quot;{doc.snippet}&quot;
                      </div>
                    </div>
                  ))
                )}
              </motion.div>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Main Feed: Recently Modified */}
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 }}
              className="lg:col-span-2 space-y-6"
            >
              <h3 className="text-xl font-bold text-white uppercase tracking-widest flex items-center gap-3">
                <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                Recently Ingested Streams
              </h3>
              
              <div className="space-y-3">
                {data.recent_documents.map((doc, idx) => (
                  <div 
                    key={idx}
                    onClick={() => onSelectEntity && onSelectEntity({ id: doc.id, name: doc.name, type: 'file' })}
                    className="group bg-zinc-900/40 border border-white/5 hover:border-cyan-500/40 hover:bg-zinc-900 rounded-lg p-4 transition-all flex justify-between items-center cursor-pointer shadow-sm hover:shadow-[0_0_15px_rgba(34,211,238,0.1)]"
                  >
                    <div className="flex flex-col gap-1 overflow-hidden">
                      <span className="text-xs font-bold text-cyan-400 uppercase tracking-wider">
                        {doc.category}
                      </span>
                      <span className="font-medium text-white truncate group-hover:text-cyan-100 transition-colors">
                        {doc.name}
                      </span>
                    </div>
                    <div className="text-[10px] text-zinc-500 font-mono tracking-widest shrink-0 ml-4">
                      {formatModifiedDate(doc.last_modified, { month: 'short', day: 'numeric' })}
                    </div>
                  </div>
                ))}
                {data.recent_documents.length === 0 && (
                  <div className="text-zinc-500 italic text-sm p-4 border border-dashed border-white/10 rounded-lg text-center">
                    No recent streams found in the DB.
                  </div>
                )}
              </div>
            </motion.div>

            {/* Sidebar: Categories */}
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2 }}
              className="space-y-6"
            >
              <h3 className="text-xl font-bold text-white uppercase tracking-widest flex items-center gap-3">
                <span className="w-2 h-2 rounded-full bg-fuchsia-500 animate-pulse" />
                Primary Clusters
              </h3>
              
              <div className="grid grid-cols-1 gap-3">
                {data.categories.map((cat, idx) => (
                  <div 
                    key={idx}
                    onClick={() => handleCategoryClick(cat.name)}
                    className="bg-zinc-950/80 border border-white/10 rounded-lg p-3 flex justify-between items-center hover:border-fuchsia-500/50 transition-colors group cursor-pointer"
                  >
                    <span className="text-sm font-semibold text-zinc-300 group-hover:text-white truncate pr-4">
                      {cat.name}
                    </span>
                    <span className="bg-white/5 group-hover:bg-fuchsia-500/20 text-zinc-400 group-hover:text-fuchsia-300 text-[10px] font-bold px-2 py-1 rounded-full transition-colors shrink-0">
                      {cat.count}
                    </span>
                  </div>
                ))}
              </div>
            </motion.div>
          </div>
        )}
      </div>
    </div>
  );
}
