# 🎨 UI & Styling Style Guide

This document details the sci-fi dashboard design guidelines, CSS layout patterns, color tokens, and animation standards used in the `Navis-Web` frontend.

---

## 🌌 Core Theme & Concept

Navis-Web utilizes a **Tactical Sci-Fi Cockpit** aesthetic. It relies on high contrast, glowing borders, transparent backdrops, and active status widgets to simulate a physical Command Bridge.

---

## 🎨 Color Token Registry

Accents are categorized by functional sectors:

| System Pillar | Color Hex | CSS Class | Visual Effect |
| :--- | :--- | :--- | :--- |
| **Command / Sanctum** | `#00d4ff` | `text-accent` / `bg-accent` | Cybernetic Cyan glow |
| **Combat / Threats** | `#ff4d4d` | `text-red-500` / `bg-red-500` | Critical Warning Red glow |
| **Beasts / Regional** | `#f59e0b` | `text-amber-500` / `bg-amber-500` | Warning Amber aura |
| **Dark Backdrops** | `#09090b` | `bg-zinc-950` / `bg-zinc-900` | Space Black / Charcoal matte |
| **Borders** | `rgba(255,255,255,0.1)` | `border-white/10` | Sleek outline highlights |

---

## 🪟 Sci-Fi Glassmorphism

To construct standard panel backdrops, combine blur filters and semi-transparent fills:
```html
<div className="bg-zinc-950/90 backdrop-blur-md border border-white/10 rounded-lg shadow-2xl">
  <!-- Content -->
</div>
```

To create high-fidelity glows (e.g. active targets):
```css
box-shadow: 0 0 15px rgba(0, 212, 255, 0.4); /* Cyan Accent */
box-shadow: 0 0 15px rgba(255, 77, 77, 0.4);  /* Red Warning */
```

---

## 🧬 Interface Anatomy

The Next.js layout ([page.js](file:///c:/Projects/Navis-Web/frontend/src/app/page.js)) is divided into 4 hierarchal levels:

1. **Level 1: Sovereign Ribbon**
   - Header tracking real-time calendar coordinates, the active context, and sync parameters.
2. **Level 2: Sector Rail**
   - Leftmost navigational bar directing users between System pillars (Sanctum, Combat, Facilities).
3. **Level 3: Entity Rail**
   - Secondary file explorer list displaying files (e.g. daily logs) or custom blueprints.
4. **Level 4: Central Tactical Viewport**
   - The primary viewport ([SectorView.js](file:///c:/Projects/Navis-Web/frontend/src/components/SectorView.js)) rendering active Markdown dossiers, the Battle Field terminal, or configuration settings.

---

## 🎬 Animation Guidelines

We utilize `framer-motion` for transitions. Micro-interactions should be swift, sharp, and clean:
- **Default Fade/Scale Transition:**
  ```javascript
  const transition = { duration: 0.2, ease: "easeOut" };
  ```
- **Active state hover shifts:** Translate elements slightly upward (`-translate-y-1`) or scale up marginally (`scale-[1.02]`) on hover to indicate interactiveness.
