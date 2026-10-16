"use client";

import { useState, useEffect, Fragment } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { apiFetch, apiUrl, vaultAssetUrl } from "../../lib/desktopApi";

export default function PrismNexus() {
  const [loungeData, setLoungeData] = useState({
    books: null,
    movies: null,
    tv: null,
    youtube: null,
    audio: null,
    games: null
  });
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [activeTab, setActiveTab] = useState("books");
  const [groupBy, setGroupBy] = useState("None");
  const [filterGenre, setFilterGenre] = useState("All");
  const [filterAuthor, setFilterAuthor] = useState("All");

  const tabs = [
    { id: "books", label: "Books", icon: "📚" },
    { id: "movies", label: "Movies", icon: "🎬" },
    { id: "tv", label: "TV Shows", icon: "📺" },
    { id: "games", label: "Games", icon: "🎮" },
    { id: "audio", label: "Audio", icon: "🎧" },
    { id: "youtube", label: "YouTube", icon: "▶️" },
  ];

  useEffect(() => {
    const fetchData = async () => {
      try {

        const [booksRes, youtubeRes, moviesRes, tvRes, audioRes, gamesRes] = await Promise.all([
          apiFetch("/api/v1/lounge/media?type=books"),
          apiFetch("/api/v1/lounge/media?type=youtube"),
          apiFetch("/api/v1/lounge/media?type=movies"),
          apiFetch("/api/v1/lounge/media?type=tv"),
          apiFetch("/api/v1/lounge/media?type=audio"),
          apiFetch("/api/v1/lounge/media?type=games")
        ]);

        const [bData, yData, mData, tData, aData, gData] = await Promise.all([
           booksRes.ok ? booksRes.json() : null,
           youtubeRes.ok ? youtubeRes.json() : null,
           moviesRes.ok ? moviesRes.json() : null,
           tvRes.ok ? tvRes.json() : null,
           audioRes.ok ? audioRes.json() : null,
           gamesRes.ok ? gamesRes.json() : null
        ]);

        setLoungeData({
          books: bData,
          youtube: yData,
          movies: mData,
          tv: tData,
          audio: aData,
          games: gData
        });
      } catch (err) {
        console.error("Failed to fetch data:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  // Reset filters when tab changes
  useEffect(() => {
    setGroupBy("None");
    setFilterGenre("All");
    setFilterAuthor("All");
    setSearchTerm("");
  }, [activeTab]);

  const getGradientForTitle = (title) => {
    // Generate a consistent but distinct gradient angle based on title string length
    const val = [...title].reduce((acc, char) => acc + char.charCodeAt(0), 0);
    const angle = val % 360;
    // Base color for books
    const scheme = [`#3b82f6`, `#1d4ed8`];
    return `linear-gradient(${angle}deg, ${scheme[0]}40, ${scheme[1]}90)`;
  };



  const renderBookCard = (item, idx) => {

    const posterUrl = item.poster_url || apiUrl(`/api/v1/lounge/media/${item.id}/poster`);

    return (
      <motion.div
        key={item.id}
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: (idx % 20) * 0.05 }}
        whileHover={{ scale: 1.05, y: -5 }}
        className="group relative rounded-xl overflow-hidden shadow-[0_0_15px_rgba(0,0,0,0.5)] border border-white/10 bg-zinc-950/80 cursor-pointer"
        title={item.overview || "No review"}
      >
        <div className="aspect-[2/3] w-full relative">
          <div
            className="absolute inset-0 z-0 opacity-50 group-hover:opacity-80 transition-opacity"
            style={{ background: getGradientForTitle(item.title) }}
          />
          <img
            key={`${item.id}-img`}
            src={posterUrl}
            alt={item.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-all duration-300"
            onError={(e) => {
                e.target.onerror = null;
                e.target.src = `https://placehold.co/400x600/18181b/ffffff?text=${encodeURIComponent(item.title.split(' ').join('\\n'))}&font=playfair-display`;
            }}
          />

          <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/40 to-transparent z-10" />

          <div className="absolute bottom-0 left-0 right-0 p-4 z-20">
            {item.status === 'pending' && (
              <span className="inline-block px-2 py-0.5 mb-1 rounded text-[10px] font-bold uppercase tracking-widest bg-white/20 text-white backdrop-blur-md border border-white/30">
                Up Next
              </span>
            )}
            {item.status === 'in-progress' && (
              <span className="inline-block px-2 py-0.5 mb-1 rounded text-[10px] font-bold uppercase tracking-widest bg-accent/20 text-accent backdrop-blur-md border border-accent/30 animate-pulse">
                Reading
              </span>
            )}
            {item.status === 'completed' && (
              <span className="inline-block px-2 py-0.5 mb-1 rounded text-[10px] font-bold uppercase tracking-widest bg-green-500/20 text-green-400 backdrop-blur-md border border-green-500/30">
                Read {item.rating > 0 ? `★${item.rating}` : ''}
              </span>
            )}

            <h4 className="font-bold text-sm leading-tight text-white line-clamp-2 drop-shadow-md">
              {item.title}
            </h4>
            <p className="text-xs text-zinc-300 mt-1 line-clamp-1">{item.creator}</p>
          </div>
        </div>
      </motion.div>
    );
  };

  const renderYouTubeCard = (item, idx) => {

    const posterUrl = item.poster_url || apiUrl(`/api/v1/lounge/media/${item.id}/poster`);
    return (
      <motion.div
        key={item.id}
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: (idx % 20) * 0.05 }}
        whileHover={{ scale: 1.05, y: -5 }}
        className="group relative rounded-xl overflow-hidden shadow-[0_0_15px_rgba(0,0,0,0.5)] border border-white/10 bg-zinc-950/80 cursor-pointer aspect-video"
      >
        <img
          src={posterUrl}
          alt={item.title}
          className="w-full h-full object-cover group-hover:scale-105 transition-all duration-300"
          onError={(e) => {
              e.target.onerror = null;
              e.target.src = `https://placehold.co/640x360/18181b/ffffff?text=${encodeURIComponent(item.title)}`;
          }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/40 to-transparent z-10" />

        <div className="absolute bottom-0 left-0 right-0 p-3 z-20">
          <span className="inline-block px-1.5 py-0.5 mb-1 rounded-sm text-[9px] font-bold uppercase tracking-widest bg-red-500/20 text-red-400 backdrop-blur-md border border-red-500/30">
            {item.creator || "YouTube"}
          </span>
          <h4 className="font-bold text-xs leading-tight text-white line-clamp-2 drop-shadow-md">
            {item.title}
          </h4>
        </div>
        {item.duration_mins > 0 && (
          <div className="absolute top-2 right-2 bg-black/60 px-1.5 py-0.5 rounded text-[10px] font-mono text-white z-20 backdrop-blur-md">
            {item.duration_mins}m
          </div>
        )}
      </motion.div>
    );
  };

  const renderJellyfinCard = (item, idx, type) => {

    const posterUrl = item.poster_url || apiUrl(`/api/v1/lounge/media/${item.id}/poster`);

    return (
      <motion.div
        key={item.id}
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: (idx % 20) * 0.05 }}
        whileHover={{ scale: 1.05, y: -5 }}
        className="group relative rounded-xl overflow-hidden shadow-[0_0_15px_rgba(0,0,0,0.5)] border border-white/10 bg-zinc-950/80 cursor-pointer"
        title={item.overview || "No overview"}
      >
        <div className="aspect-[2/3] w-full relative">
          <div
            className="absolute inset-0 z-0 opacity-50 group-hover:opacity-80 transition-opacity"
            style={{ background: getGradientForTitle(item.title) }}
          />
          <img
            key={`${item.id}-img`}
            src={posterUrl}
            alt={item.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-all duration-300"
            onError={(e) => {
                e.target.onerror = null;
                e.target.src = `https://placehold.co/400x600/18181b/ffffff?text=${encodeURIComponent(item.title.split(' ').join('\\n'))}&font=playfair-display`;
            }}
          />

          <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/40 to-transparent z-10" />

          <div className="absolute bottom-0 left-0 right-0 p-4 z-20">
            {item.rating > 0 && (
              <span className="inline-block px-2 py-0.5 mb-1 rounded text-[10px] font-bold uppercase tracking-widest bg-yellow-500/20 text-yellow-400 backdrop-blur-md border border-yellow-500/30">
                ★ {item.rating.toFixed(1)}
              </span>
            )}

            <h4 className="font-bold text-sm leading-tight text-white line-clamp-2 drop-shadow-md">
              {item.title}
            </h4>
            <p className="text-xs text-zinc-300 mt-1 line-clamp-1">{item.release_year}</p>
          </div>
          {item.duration_mins > 0 && (
            <div className="absolute top-2 right-2 bg-black/60 px-1.5 py-0.5 rounded text-[10px] font-mono text-white z-20 backdrop-blur-md">
              {item.duration_mins}m
            </div>
          )}
        </div>
      </motion.div>
    );
  };

  const renderAudioCard = (item, idx) => {

    const posterUrl = item.poster_url || apiUrl(`/api/v1/lounge/media/${item.id}/poster`);

    return (
      <motion.div
        key={item.id}
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: (idx % 20) * 0.05 }}
        whileHover={{ scale: 1.05, y: -5 }}
        className="group relative rounded-xl overflow-hidden shadow-[0_0_15px_rgba(0,0,0,0.5)] border border-white/10 bg-zinc-950/80 cursor-pointer"
        title={item.title}
      >
        <div className="aspect-square w-full relative">
          <div
            className="absolute inset-0 z-0 opacity-50 group-hover:opacity-80 transition-opacity"
            style={{ background: getGradientForTitle(item.title) }}
          />
          <img
            key={`${item.id}-img`}
            src={posterUrl}
            alt={item.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-all duration-300"
            onError={(e) => {
                e.target.onerror = null;
                e.target.src = `https://placehold.co/400x400/18181b/ffffff?text=${encodeURIComponent(item.title.split(' ').join('\\n'))}&font=playfair-display`;
            }}
          />

          <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/40 to-transparent z-10" />

          <div className="absolute bottom-0 left-0 right-0 p-4 z-20">
            <span className="inline-block px-2 py-0.5 mb-1 rounded text-[10px] font-bold uppercase tracking-widest bg-cyan-500/20 text-cyan-400 backdrop-blur-md border border-cyan-500/30">
              Audiobook
            </span>
            <h4 className="font-bold text-sm leading-tight text-white line-clamp-2 drop-shadow-md">
              {item.title}
            </h4>
            {item.creator && (
              <p className="text-xs text-zinc-300 mt-1 line-clamp-1">{item.creator}</p>
            )}
          </div>
          {item.duration_mins > 0 && (
            <div className="absolute top-2 right-2 bg-black/60 px-1.5 py-0.5 rounded text-[10px] font-mono text-white z-20 backdrop-blur-md">
              {Math.floor(item.duration_mins / 60)}h {item.duration_mins % 60}m
            </div>
          )}
        </div>
      </motion.div>
    );
  };

  const renderGameCard = (item, idx) => {

    const posterUrl = item.poster_url || apiUrl(`/api/v1/lounge/media/${item.id}/poster`);

    return (
      <motion.div
        key={item.id}
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: (idx % 20) * 0.05 }}
        whileHover={{ scale: 1.05, y: -5 }}
        className="group relative rounded-xl overflow-hidden shadow-[0_0_15px_rgba(0,0,0,0.5)] border border-white/10 bg-zinc-950/80 cursor-pointer aspect-[3/4]"
      >
        <div className="w-full h-full relative">
          <div
            className="absolute inset-0 z-0 opacity-50 group-hover:opacity-80 transition-opacity"
            style={{ background: getGradientForTitle(item.title) }}
          />
          <img
            key={`${item.id}-img`}
            src={posterUrl}
            alt={item.title}
            className="w-full h-full object-cover group-hover:scale-105 transition-all duration-300"
            onError={(e) => {
                e.target.onerror = null;
                e.target.src = `https://placehold.co/600x800/18181b/ffffff?text=${encodeURIComponent(item.title.split(' ').join('\\n'))}&font=playfair-display`;
            }}
          />

          <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/50 to-transparent z-10" />

          <div className="absolute bottom-0 left-0 right-0 p-4 z-20">
            <span className="inline-block px-2 py-0.5 mb-1 rounded text-[10px] font-bold uppercase tracking-widest bg-emerald-500/20 text-emerald-400 backdrop-blur-md border border-emerald-500/30">
              {item.source === "Disk" ? "Archive" : item.source}
            </span>
            <h4 className="font-bold text-sm leading-tight text-white drop-shadow-md">
              {item.title}
            </h4>
          </div>
        </div>
      </motion.div>
    );
  };

  const renderContent = () => {
    const data = loungeData[activeTab];

    // For unmapped tabs
    if (!["books", "youtube", "movies", "tv", "audio", "games"].includes(activeTab)) {
      const currentTabInfo = tabs.find(t => t.id === activeTab);
      return (
        <div className="text-center py-32 border border-white/5 border-dashed rounded-2xl bg-zinc-900/20">
          <div className="text-4xl mb-4 opacity-50">{currentTabInfo?.icon}</div>
          <h3 className="text-xl font-bold text-white mb-2 uppercase tracking-widest">{currentTabInfo?.label} Storage Offline</h3>
          <p className="text-zinc-500 font-mono text-sm uppercase tracking-widest">Awaiting database uplink...</p>
        </div>
      );
    }

    if (!data || !data.items || data.items.length === 0) {
      return <div className="text-center py-20 text-zinc-500 font-mono text-sm uppercase tracking-widest">[ Library Empty ]</div>;
    }

    let filteredItems = data.items.filter(item =>
      item.title?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      item.creator?.toLowerCase().includes(searchTerm.toLowerCase())
    );

    const allGenres = [...new Set(data.items.flatMap(item => item.genres || []))].sort();
    const allAuthors = [...new Set(data.items.map(item => item.creator).filter(c => c))].sort();

    if (filterGenre !== "All") {
      filteredItems = filteredItems.filter(item => item.genres?.includes(filterGenre));
    }
    if (filterAuthor !== "All") {
      filteredItems = filteredItems.filter(item => item.creator === filterAuthor);
    }

    const renderControls = () => (
      <div className="flex flex-col md:flex-row gap-4 justify-between mb-8 bg-zinc-900/50 p-4 rounded-xl border border-white/5">
        <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center">
          <input
            type="text"
            placeholder="Search..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full sm:max-w-xs px-4 py-2 rounded-full bg-zinc-950 border border-white/10 text-white focus:outline-none focus:border-white/30 placeholder-zinc-500 font-mono text-sm shadow-inner"
          />
          <div className="flex gap-2">
            <select
              value={filterGenre}
              onChange={(e) => setFilterGenre(e.target.value)}
              className="px-3 py-2 rounded-lg bg-zinc-950 border border-white/10 text-white font-mono text-xs focus:outline-none focus:border-white/30"
            >
              <option value="All">All Genres</option>
              {allGenres.map(g => <option key={g} value={g}>{g}</option>)}
            </select>
            <select
              value={filterAuthor}
              onChange={(e) => setFilterAuthor(e.target.value)}
              className="px-3 py-2 rounded-lg bg-zinc-950 border border-white/10 text-white font-mono text-xs focus:outline-none focus:border-white/30"
            >
              <option value="All">All Authors</option>
              {allAuthors.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-zinc-500 font-mono text-xs uppercase tracking-widest">Group By:</span>
          <div className="flex bg-zinc-950 rounded-lg p-1 border border-white/10">
            {["None", "Author", "Series", "Genre"].map(mode => (
              <button
                key={mode}
                onClick={() => setGroupBy(mode)}
                className={`px-3 py-1.5 rounded-md font-mono text-xs uppercase tracking-widest transition-colors ${groupBy === mode ? 'bg-white/10 text-white' : 'text-zinc-500 hover:text-zinc-300'}`}
              >
                {mode}
              </button>
            ))}
          </div>
        </div>
      </div>
    );

    const groupItems = (items) => {
      if (groupBy === "None") return { "All": items };

      const groups = {};
      items.forEach(item => {
        let keys = [];
        if (groupBy === "Author") keys = [item.creator || "Unknown"];
        else if (groupBy === "Series") keys = [item.series || "No Series"];
        else if (groupBy === "Genre") keys = item.genres?.length > 0 ? item.genres : ["Uncategorized"];

        keys.forEach(key => {
          if (!groups[key]) groups[key] = [];
          groups[key].push(item);
        });
      });
      return groups;
    };

    const groupedData = groupItems(filteredItems);

    if (activeTab === "movies" || activeTab === "tv") {
      const typeLabel = activeTab === "movies" ? "Movies" : "TV Shows";
      const color = activeTab === "movies" ? "bg-amber-500" : "bg-purple-500";

      const activeItems = filteredItems.filter(item => item.source === "Jellyfin");
      const archiveItems = filteredItems.filter(item => item.source !== "Jellyfin");

      return (
        <div className="space-y-12 pb-12">
          {renderControls()}

          {Object.entries(groupedData).map(([groupName, items]) => {
            const activeItems = items.filter(item => item.source === "Jellyfin");
            const archiveItems = items.filter(item => item.source !== "Jellyfin");
            if (activeItems.length === 0 && archiveItems.length === 0) return null;

            return (
              <div key={groupName} className="bg-zinc-950/40 p-6 rounded-2xl border border-white/5">
                {groupBy !== "None" && (
                  <h2 className="text-2xl font-bold text-white mb-6 uppercase tracking-widest border-b border-white/10 pb-4">{groupName}</h2>
                )}

                {activeItems.length > 0 && (
                  <div className="mb-8">
                    <h3 className="text-xl font-bold text-white mb-6 uppercase tracking-widest border-b border-white/10 pb-2 flex items-center gap-3">
                      <span className={`w-2 h-2 rounded-full ${color} animate-pulse`} />
                      Active Roster
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6">
                      {activeItems.map((item, idx) => renderJellyfinCard(item, idx, activeTab))}
                    </div>
                  </div>
                )}

                {archiveItems.length > 0 && (
                  <div>
                    <h3 className="text-xl font-bold text-white mb-6 uppercase tracking-widest border-b border-white/10 pb-2 flex items-center gap-3">
                      <span className="w-2 h-2 rounded-full bg-zinc-600" />
                      Archive
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6 opacity-80">
                      {archiveItems.map((item, idx) => renderJellyfinCard(item, idx, activeTab))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      );
    }

    if (activeTab === "audio") {
      return (
        <div className="space-y-12 pb-12">
          {renderControls()}

          {Object.entries(groupedData).map(([groupName, items]) => {
            const activeAudio = items.filter(item => item.overview && item.overview.includes("G:\\My Drive"));
            const archiveAudio = items.filter(item => !item.overview || !item.overview.includes("G:\\My Drive"));
            if (activeAudio.length === 0 && archiveAudio.length === 0) return null;

            return (
              <div key={groupName} className="bg-zinc-950/40 p-6 rounded-2xl border border-white/5">
                {groupBy !== "None" && (
                  <h2 className="text-2xl font-bold text-white mb-6 uppercase tracking-widest border-b border-white/10 pb-4">{groupName}</h2>
                )}

                {activeAudio.length > 0 && (
                  <div className="mb-8">
                    <h3 className="text-xl font-bold text-white mb-6 uppercase tracking-widest border-b border-white/10 pb-2 flex items-center gap-3">
                      <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
                      Active Roster
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6">
                      {activeAudio.map((item, idx) => renderAudioCard(item, idx))}
                    </div>
                  </div>
                )}

                {archiveAudio.length > 0 && (
                  <div>
                    <h3 className="text-xl font-bold text-white mb-6 uppercase tracking-widest border-b border-white/10 pb-2 flex items-center gap-3">
                      <span className="w-2 h-2 rounded-full bg-zinc-600" />
                      Archive
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6 opacity-80">
                      {archiveAudio.map((item, idx) => renderAudioCard(item, idx))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      );
    }

    if (activeTab === "youtube") {
      return (
        <div className="space-y-12 pb-12">
          {renderControls()}

          {Object.entries(groupedData).map(([groupName, items]) => {
            if (items.length === 0) return null;
            return (
              <div key={groupName} className="bg-zinc-950/40 p-6 rounded-2xl border border-white/5">
                {groupBy !== "None" && (
                  <h2 className="text-2xl font-bold text-white mb-6 uppercase tracking-widest border-b border-white/10 pb-4">{groupName}</h2>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                  {items.map((v, i) => renderYouTubeCard(v, i))}
                </div>
              </div>
            );
          })}
        </div>
      );
    }

    if (activeTab === "books") {
      return (
        <div className="space-y-12 pb-12">
          {renderControls()}

          {Object.entries(groupedData).map(([groupName, items]) => {
            const readBooks = items.filter(b => b.status === "completed");
            const readingBooks = items.filter(b => b.status === "in-progress");
            const toReadBooks = items.filter(b => b.status === "pending");

            if (readBooks.length === 0 && readingBooks.length === 0 && toReadBooks.length === 0) return null;

            return (
              <div key={groupName} className="bg-zinc-950/40 p-6 rounded-2xl border border-white/5">
                {groupBy !== "None" && (
                  <h2 className="text-2xl font-bold text-white mb-6 uppercase tracking-widest border-b border-white/10 pb-4">{groupName}</h2>
                )}

                {readingBooks.length > 0 && (
                  <div className="mb-8">
                    <h3 className="text-xl font-bold text-white mb-6 uppercase tracking-widest border-b border-white/10 pb-2 flex items-center gap-3">
                      <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
                      Currently Parsing
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6">
                      {readingBooks.map((b, i) => renderBookCard(b, i))}
                    </div>
                  </div>
                )}

                {readBooks.length > 0 && (
                  <div className="mb-8">
                    <h3 className="text-xl font-bold text-white mb-6 uppercase tracking-widest border-b border-white/10 pb-2 flex items-center gap-3">
                      <span className="w-2 h-2 rounded-full bg-blue-500/50" />
                      Archived Knowledge
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6">
                      {readBooks.map((b, i) => renderBookCard(b, i))}
                    </div>
                  </div>
                )}

                {toReadBooks.length > 0 && (
                  <div>
                    <h3 className="text-xl font-bold text-white mb-6 uppercase tracking-widest border-b border-white/10 pb-2 flex items-center gap-3">
                      <span className="w-2 h-2 rounded-full bg-blue-900" />
                      Awaiting Uplink
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6 opacity-60">
                      {toReadBooks.map((b, i) => renderBookCard(b, i))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      );
    }

    if (activeTab === "games") {
      return (
        <div className="space-y-12 pb-12">
          {renderControls()}

          {Object.entries(groupedData).map(([groupName, items]) => {
            const activeGames = items.filter(item => item.source !== "Disk");
            const archiveGames = items.filter(item => item.source === "Disk");
            if (activeGames.length === 0 && archiveGames.length === 0) return null;

            return (
              <div key={groupName} className="bg-zinc-950/40 p-6 rounded-2xl border border-white/5">
                {groupBy !== "None" && (
                  <h2 className="text-2xl font-bold text-white mb-6 uppercase tracking-widest border-b border-white/10 pb-4">{groupName}</h2>
                )}

                {activeGames.length > 0 && (
                  <div className="mb-8">
                    <h3 className="text-xl font-bold text-white mb-6 uppercase tracking-widest border-b border-white/10 pb-2 flex items-center gap-3">
                      <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                      Active Roster
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6">
                      {activeGames.map((item, idx) => renderGameCard(item, idx))}
                    </div>
                  </div>
                )}

                {archiveGames.length > 0 && (
                  <div>
                    <h3 className="text-xl font-bold text-white mb-6 uppercase tracking-widest border-b border-white/10 pb-2 flex items-center gap-3">
                      <span className="w-2 h-2 rounded-full bg-zinc-600" />
                      Cold Storage
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-6 opacity-80">
                      {archiveGames.map((item, idx) => renderGameCard(item, idx))}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      );
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-white p-8 font-sans">
      <div className="max-w-[1600px] mx-auto">

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <div className="w-full h-48 md:h-64 rounded-2xl overflow-hidden mb-6 relative shadow-[0_0_20px_rgba(236,72,153,0.3)] border border-white/10">
            <img
              src={vaultAssetUrl('Lounge/Landscape.png')}
              alt="Boba Lounge Landscape"
              className="w-full h-full object-cover"
              onError={(e) => { e.target.style.display = 'none'; }}
            />
            <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-zinc-950/20 to-transparent" />
          </div>

          <h1 className="text-5xl font-black tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-fuchsia-500 via-pink-400 to-rose-400 flex items-center gap-4 drop-shadow-[0_0_15px_rgba(236,72,153,0.3)]">
            <span>🧋</span> Boba Lounge
          </h1>
          <p className="text-zinc-400 mt-2 font-mono uppercase tracking-widest text-sm">
            High-Fidelity Media & Sensory Curation
          </p>
        </motion.div>

        {/* Navigation Tabs */}
        <div className="flex gap-2 overflow-x-auto pb-4 mb-8 custom-scrollbar">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-6 py-3 rounded-xl font-bold uppercase tracking-wider text-xs transition-all flex items-center gap-2 whitespace-nowrap ${
                activeTab === tab.id
                  ? 'bg-fuchsia-500 text-white shadow-[0_0_15px_rgba(236,72,153,0.5)]'
                  : 'bg-zinc-900 text-zinc-400 hover:bg-zinc-800 border border-white/5 hover:border-white/20'
              }`}
            >
              <span className="text-lg">{tab.icon}</span> {tab.label}
            </button>
          ))}
        </div>

        {/* Media Grid */}
        {loading ? (
          <div className="flex justify-center items-center h-64">
            <div className="flex flex-col items-center gap-4">
              <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-fuchsia-500"></div>
              <div className="text-xs font-mono text-fuchsia-400 uppercase tracking-[0.2em] animate-pulse">
                Parsing manifests...
              </div>
            </div>
          </div>
        ) : (
          <AnimatePresence mode="wait">
            <motion.div
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.2 }}
            >
              {renderContent()}
            </motion.div>
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
