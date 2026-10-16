'use client';

import React, { useEffect, useState } from 'react';
import { apiUrl, vaultAssetUrl } from '../lib/desktopApi';

export default function VaultAssetImage({
  assetPath,
  fallbackPaths = [],
  sourceUrls,
  alt = '',
  className = '',
  fallbackClassName = '',
  cacheBust = false,
  ...props
}) {
  const paths = sourceUrls?.length ? sourceUrls.filter(Boolean) : [assetPath, ...fallbackPaths].filter(Boolean);
  const fallbackKey = fallbackPaths.join('|');
  const sourceUrlsKey = sourceUrls?.join('|') || '';
  const [pathIndex, setPathIndex] = useState(0);

  useEffect(() => setPathIndex(0), [assetPath, fallbackKey, sourceUrlsKey]);

  if (!paths[pathIndex]) {
    return (
      <div
        role="img"
        aria-label={alt || 'Image unavailable'}
        className={`flex items-center justify-center bg-zinc-900 text-white/30 text-[10px] font-mono uppercase tracking-widest ${fallbackClassName}`}
      >
        Image unavailable
      </div>
    );
  }

  return (
    <img
      {...props}
      src={sourceUrls?.length ? apiUrl(paths[pathIndex]) : vaultAssetUrl(paths[pathIndex], { cacheBust })}
      alt={alt}
      className={className}
      onError={() => setPathIndex((current) => current + 1)}
    />
  );
}
