'use client';

export default function NativeCapabilityNotice({ feature, className = '' }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`rounded-lg border border-amber-400/20 bg-amber-400/5 px-4 py-3 text-sm text-amber-100/80 ${className}`}
    >
      {feature} is unavailable in the desktop app because its native provider transport is not configured. Open Navis in web mode with the backend running to use this feature.
    </div>
  );
}
