"use client";

import { useState, useEffect, Fragment } from "react";
import { motion } from "framer-motion";
import { apiFetch, vaultAssetUrl } from "../../../lib/desktopApi";

export default function IronSanctum() {
  const [vitals, setVitals] = useState([]);
  const [exercises, setExercises] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [vitalsRes, exerciseRes] = await Promise.all([
          apiFetch("/api/v1/biometrics/vitals/history?limit=7"),
          apiFetch("/api/v1/biometrics/exercises/recent?limit=5")
        ]);

        if (vitalsRes.ok) {
          const data = await vitalsRes.json();
          setVitals(data.value || data);
        }
        if (exerciseRes.ok) {
          const eData = await exerciseRes.json();
          setExercises(eData.value || eData);
        }
      } catch (err) {
        console.error("Failed to fetch data:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const formatSleep = (minutes) => {
    if (!minutes) return "--";
    const h = Math.floor(minutes / 60);
    const m = minutes % 60;
    return `${h}h ${m}m`;
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-white p-8 font-sans">
      <div className="max-w-6xl mx-auto">


        {loading ? (
          <div className="flex justify-center items-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-emerald-500"></div>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            {vitals.slice(0, 1).map((latest, i) => (
              <Fragment key={i}>
                <MetricCard title="Steps" value={latest.steps?.toLocaleString() || "0"} icon="🏃" color="emerald" />
                <MetricCard title="Calories" value={Math.round(latest.calories || 0).toLocaleString()} icon="🔥" color="orange" />
                <MetricCard title="Sleep" value={formatSleep(latest.sleep_minutes)} icon="😴" color="indigo" subValue={`${latest.sleep_efficiency}% Eff`} />
                <MetricCard title="Avg HR" value={`${latest.avg_hr || "--"} bpm`} icon="💓" color="rose" />
              </Fragment>
            ))}
          </div>
        )}

        <div className="bg-zinc-950/90 backdrop-blur-md border border-white/10 rounded-xl p-6 shadow-2xl">
          <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
            <span>📊</span> Recent Performance
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-white/10 text-zinc-400 text-sm">
                  <th className="pb-3 px-4 font-medium">Date</th>
                  <th className="pb-3 px-4 font-medium">Steps</th>
                  <th className="pb-3 px-4 font-medium">Calories</th>
                  <th className="pb-3 px-4 font-medium">Sleep</th>
                  <th className="pb-3 px-4 font-medium">Avg HR</th>
                </tr>
              </thead>
              <tbody>
                {vitals.map((v, i) => (
                  <motion.tr
                    key={v.date}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.1 }}
                    className="border-b border-white/5 hover:bg-white/5 transition-colors"
                  >
                    <td className="py-4 px-4 font-mono text-sm">{v.date}</td>
                    <td className="py-4 px-4">{v.steps?.toLocaleString() || "--"}</td>
                    <td className="py-4 px-4">{Math.round(v.calories || 0).toLocaleString()}</td>
                    <td className="py-4 px-4">
                      <span className="flex items-center gap-2">
                        {formatSleep(v.sleep_minutes)}
                        {v.sleep_efficiency > 0 && (
                          <span className="text-xs px-2 py-1 bg-white/10 rounded-full text-zinc-300">
                            {v.sleep_efficiency}%
                          </span>
                        )}
                      </span>
                    </td>
                    <td className="py-4 px-4 text-rose-400">{v.avg_hr || "--"}</td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Strength / Exercises Section */}
        <div className="bg-zinc-950/90 backdrop-blur-md border border-white/10 rounded-xl p-6 shadow-2xl mt-8">
          <h2 className="text-xl font-semibold mb-6 flex items-center gap-2">
            <span>🏋️</span> Recent Operations (Kinetic)
          </h2>
          {exercises && exercises.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {exercises.map((ex, i) => (
                <motion.div
                  key={`${ex.date}-${i}`}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1 }}
                  className="p-4 border border-white/10 bg-white/5 rounded-lg flex flex-col"
                >
                  <div className="flex justify-between items-center mb-2">
                    <span className="font-bold text-emerald-400">{ex.activity_name || "Exercise"}</span>
                    <span className="text-xs text-zinc-400">{ex.date}</span>
                  </div>
                  <div className="text-sm text-zinc-300">
                    <div>Duration: <span className="text-white">{ex.duration_minutes}m</span></div>
                    <div>Calories: <span className="text-white">{Math.round(ex.calories)} 🔥</span></div>
                    {ex.avg_hr && <div>Avg HR: <span className="text-white">{ex.avg_hr} 💓</span></div>}
                  </div>
                </motion.div>
              ))}
            </div>
          ) : (
            <p className="text-zinc-500 italic">No recent physical operations detected in the manifest.</p>
          )}
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-8 pt-4 border-t border-white/10"
        >
          <div className="w-full rounded-xl overflow-hidden shadow-2xl relative border border-white/10">
            <img 
              src={vaultAssetUrl("Facilities/Iron Sanctum/Landscape.png")}
              alt="Iron Sanctum Profile"
              className="w-full h-auto"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-zinc-950/80 via-transparent to-transparent"></div>
          </div>
        </motion.div>

      </div>
    </div>
  );
}

function MetricCard({ title, value, icon, color, subValue }) {
  const colorMap = {
    emerald: "text-emerald-400 border-emerald-400/20 bg-emerald-400/5",
    orange: "text-orange-400 border-orange-400/20 bg-orange-400/5",
    indigo: "text-indigo-400 border-indigo-400/20 bg-indigo-400/5",
    rose: "text-rose-400 border-rose-400/20 bg-rose-400/5",
  };

  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      className={`p-6 rounded-xl border backdrop-blur-md transition-all ${colorMap[color] || "border-white/10 bg-white/5"}`}
    >
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-sm font-medium text-zinc-300">{title}</h3>
        <span className="text-xl">{icon}</span>
      </div>
      <div className="text-3xl font-bold">{value}</div>
      {subValue && <div className="text-xs mt-2 text-zinc-400">{subValue}</div>}
    </motion.div>
  );
}
