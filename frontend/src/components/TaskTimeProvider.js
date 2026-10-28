"use client";
import React, { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/desktopApi';
import { TaskTimezone } from './TaskStatusPicker';
import { navisTimezone } from '@/lib/taskCompletionTime.mjs';

export default function TaskTimeProvider({ children }) {
  const [timezone, setTimezone] = useState(null);
  useEffect(() => {
    let active = true;
    apiFetch('/api/settings').then(response => {
      if (!response.ok) throw new Error('Settings unavailable');
      return response.json();
    }).then(settings => { if (active) setTimezone(navisTimezone(settings.timezone)); })
      .catch(() => { if (active) setTimezone(navisTimezone()); });
    return () => { active = false; };
  }, []);
  return <TaskTimezone.Provider value={timezone}>{children}</TaskTimezone.Provider>;
}
