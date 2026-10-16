"use client";
import { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/desktopApi';
import { createTaskBoardStore } from './taskBoardStore.mjs';

export function useTaskBoard(endpoint, area) {
  const [state, setState] = useState({ tasks: [], loading: true, listError: '', mutationError: '', pending: false, loaded: false });
  const [store, setStore] = useState(null);
  useEffect(() => {
    const current = createTaskBoardStore(apiFetch, endpoint, area);
    setStore(current);
    const unsubscribe = current.subscribe(setState);
    current.refresh();
    return () => { unsubscribe(); current.dispose(); };
  }, [endpoint, area]);
  return { ...state, refresh: () => store?.refresh(), mutate: (...args) => store?.mutate(...args) };
}
