"use client";

import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import TaskStatusPicker from './TaskStatusPicker';
import remarkGfm from 'remark-gfm';

import rehypeRaw from 'rehype-raw';
import { apiUrl } from '../lib/desktopApi';

// Helper to recursively extract text from React components
const extractText = (node) => {
  if (!node) return '';
  if (typeof node === 'string') return node;
  if (typeof node === 'number') return String(node);
  if (Array.isArray(node)) {
    return node.map(extractText).join('');
  }
  if (React.isValidElement(node)) {
    // Skip the checkbox input rendered by remark-gfm
    if (node.type === 'input' && node.props && node.props.type === 'checkbox') {
      return '';
    }
    if (node.props && node.props.children) {
      return extractText(node.props.children);
    }
  }
  return '';
};

export default function MarkdownRenderer({ content = '', onToggleCheckbox, onHopLink }) {
  const [optimisticOverrides, setOptimisticOverrides] = useState({});

  const pendingRef = useRef(false);
  const focusAfterSave = useRef(null);
  useEffect(() => {
    if (!pending && focusAfterSave.current) {
      if (typeof document !== 'undefined') document.getElementById(focusAfterSave.current)?.focus();
      focusAfterSave.current = null;
    }
  });
  const [pending, setPending] = useState(false);
  const [saveMessage, setSaveMessage] = useState('');

  // Custom components to style the output with sci-fi theme
  const components = {
    img: ({ node, ...props }) => {
      let src = props.src;
      if (src && src.startsWith('/api/vault/')) {
        src = apiUrl(src);
      }
      return (
        <span className="block my-6 overflow-hidden rounded border border-white/10 bg-zinc-950 p-2 shadow-2xl relative group">
          <span className="absolute top-1 left-2 text-[8px] font-mono text-white/20 uppercase tracking-widest">Visual Telemetry</span>
          <img 
            {...props} 
            src={src} 
            alt={props.alt || 'Dossier Telemetry'} 
            className="max-h-[400px] w-auto mx-auto object-contain rounded mt-3 border border-white/5"
            onError={(e) => {
              // Fail-safe to avoid broken images if paths differ slightly
              e.target.style.display = 'none';
            }}
          />
        </span>
      );
    },
    h1: ({ node, ...props }) => (
      <h1 {...props} className="text-xl font-extrabold text-accent mt-8 mb-4 border-b border-accent/20 pb-2 uppercase tracking-[0.2em] flex items-center gap-2 shadow-sm font-display" />
    ),
    h2: ({ node, ...props }) => (
      <h2 {...props} className="text-base font-bold text-white mt-6 mb-3 uppercase tracking-wider border-l-2 border-accent pl-2 font-display" />
    ),
    h3: ({ node, ...props }) => (
      <h3 {...props} className="text-sm font-bold text-white/95 mt-4 mb-2 uppercase tracking-wide font-display" />
    ),
    p: ({ node, ...props }) => (
      <p {...props} className="text-sm text-white/80 leading-relaxed mb-5 font-sans" />
    ),
    ul: ({ node, ...props }) => (
      <ul {...props} className="list-none space-y-2 mb-4 pl-1" />
    ),
    ol: ({ node, ...props }) => (
      <ol {...props} className="list-decimal space-y-2 mb-4 pl-4 text-sm text-white/80 font-sans" />
    ),
    li: ({ node, checked, className, children, ...props }) => {
      let isCheckbox = (className && className.includes('task-list-item')) || checked !== undefined;
      let isChecked = checked || false;

      // Deep search to find if it's a checkbox inside a p tag
      const findCheckbox = (nodes) => {
        let found = false;
        React.Children.forEach(nodes, (child) => {
          if (React.isValidElement(child)) {
            if (child.type === 'input' && child.props.type === 'checkbox') {
              console.log("Found checkbox input with props:", child.props);
              found = true;
              isChecked = !!child.props.checked; // Always pull the checked state from the input
            } else if (child.props && child.props.children) {
              if (findCheckbox(child.props.children)) {
                found = true;
              }
            }
          }
        });
        return found;
      };

      const hasDeepCheckbox = findCheckbox(children);
      
      if (hasDeepCheckbox) {
        isCheckbox = true;
      }

      if (isCheckbox) {
        // Deep filter to remove the default checkbox
        const removeCheckbox = (nodes) => {
          return React.Children.map(nodes, (child) => {
            if (React.isValidElement(child)) {
              if (child.type === 'input' && child.props.type === 'checkbox') {
                return null;
              }
              if (child.props && child.props.children) {
                return React.cloneElement(child, {}, removeCheckbox(child.props.children));
              }
            }
            return child;
          });
        };

        const cleanChildren = removeCheckbox(children);
        const textContent = extractText(cleanChildren).trim();
        const startLine = node?.position?.start?.line;
        const itemKey = startLine != null ? `line_${startLine}` : `text_${textContent}`;
        const effectiveChecked = itemKey in optimisticOverrides ? optimisticOverrides[itemKey] : isChecked;

        const marker = (content.split(/\r?\n/)[(startLine || 1) - 1] || '').match(/<!-- navis-task:[a-f0-9]{32}:(pending|in_progress|deferred|cancelled|done) -->/);
        const taskStatus = isChecked ? 'done' : (marker?.[1] === 'done' ? 'pending' : marker?.[1] || 'pending');
        const handleCheckboxChange = async (selectedStatus) => {
          if (!onToggleCheckbox || pendingRef.current) return;
          pendingRef.current = true;
          setPending(true);
          setSaveMessage('Saving task…');
          const desired = typeof selectedStatus === 'string' ? selectedStatus : (effectiveChecked ? 'pending' : 'done');
          const nextChecked = desired === 'done';
          focusAfterSave.current = `task-status-${startLine}`;
          setOptimisticOverrides(prev => ({ ...prev, [itemKey]: nextChecked }));
          try {
            const sourceLabel = (content.split(/\r?\n/)[(startLine || 1) - 1] || '').match(/^\s*[-*+]\s+\[[ xX]\]\s+(.*)$/)?.[1] || textContent;
            const res = await onToggleCheckbox(sourceLabel, nextChecked, startLine, undefined, desired);
            setSaveMessage(res?.ok ? (res.result?.xp_status === 'pending' ? 'Task saved. XP sync pending.' : 'Task saved') : 'Save not confirmed. Review the reloaded task and retry.');
          } catch (err) {
            setSaveMessage('Save not confirmed. Reload the journal and retry.');
          } finally {
            setOptimisticOverrides(prev => {
              const copy = { ...prev };
              delete copy[itemKey];
              return copy;
            });
            pendingRef.current = false;
            setPending(false);
          }
        };

        return (
          <li className="text-sm leading-relaxed flex items-start gap-3 font-sans my-1.5">
            <input
              type="checkbox"
              checked={effectiveChecked}
              disabled={pending || !onToggleCheckbox}
              aria-busy={pending}
              onChange={handleCheckboxChange}
              className="w-4 h-4 shrink-0 mt-1 cursor-pointer accent-[#00d4ff]"
            />
            <TaskStatusPicker id={`task-status-${startLine}`} label={textContent}
              value={taskStatus} disabled={pending || !onToggleCheckbox} onChange={handleCheckboxChange} />
            <div
              className={`transition-colors duration-200 flex-1 [&>p:last-child]:mb-0 ${
                effectiveChecked ? 'text-[#888] font-normal' : 'text-white/80'
              }`}
            >
              {cleanChildren}
            </div>
          </li>
        );
      }

      // Regular list item
      return (
        <li {...props} className="text-sm text-white/80 leading-relaxed flex items-start gap-2 font-sans my-1">
          <span className="text-accent mt-1.5 shrink-0 text-[10px]">▪</span>
          <div className="flex-1 [&>p:last-child]:mb-0">{children}</div>
        </li>
      );
    },
    table: ({ node, ...props }) => (
      <div className="overflow-x-auto my-6 border border-white/10 rounded-lg shadow-xl">
        <table {...props} className="min-w-full text-xs text-left text-white/80 border-collapse font-sans" />
      </div>
    ),
    thead: ({ node, ...props }) => (
      <thead {...props} className="border-b border-white/10" />
    ),
    tr: ({ node, ...props }) => (
      <tr {...props} className="border-b border-white/5 hover:bg-white/[0.02] transition-colors" />
    ),
    th: ({ node, ...props }) => (
      <th {...props} className="px-4 py-2 bg-zinc-900 border-b border-white/10 font-bold uppercase text-accent tracking-wider text-[10px] font-display" />
    ),
    td: ({ node, ...props }) => (
      <td {...props} className="px-4 py-3 bg-zinc-950/40 text-[12px] font-medium" />
    ),
    a: ({ node, ...props }) => {
      if (props.href && props.href.startsWith('hop://')) {
        const { href, target, ...restProps } = props;
        return (
          <a 
            {...restProps} 
            href="#" 
            onClick={(e) => {
               e.preventDefault();
               e.stopPropagation();
               if (onHopLink) onHopLink(href);
            }} 
            className={"text-accent hover:underline transition-all cursor-pointer " + (props.className || "")} 
          />
        );
      }
      return <a {...props} className={"text-accent hover:underline transition-all " + (props.className || "")} target="_blank" rel="noopener noreferrer" />;
    },
    code: ({ node, className, children, ...props }) => {
      const match = /language-(\w+)/.exec(className || '');
      return !match ? (
        <code className="bg-zinc-900 border border-white/10 px-1 py-0.5 rounded text-[10px] text-accent font-mono" {...props}>
          {children}
        </code>
      ) : (
        <pre className="bg-zinc-950 border border-white/10 p-4 rounded overflow-x-auto font-mono text-[10px] text-white/80 my-4 custom-scrollbar shadow-inner">
          <code className={className} {...props}>
            {children}
          </code>
        </pre>
      );
    },
    hr: ({ node, ...props }) => (
      <hr {...props} className="border-white/10 my-8 shadow-sm" />
    ),
    blockquote: ({ node, ...props }) => (
      <blockquote {...props} className="border-l-4 border-accent bg-accent/5 p-4 my-6 rounded-r italic text-white/90 text-sm font-sans" />
    )
  };

  const handleContainerClick = (e) => {
    const anchor = e.target.closest('a');
    if (anchor && anchor.getAttribute('href')?.startsWith('hop://')) {
      e.preventDefault();
      e.stopPropagation();
      if (onHopLink) onHopLink(anchor.getAttribute('href'));
    }
  };

  // Pre-process Obsidian wikilinks into markdown links
  // [[Page Name]] -> [Page Name](hop://Page Name)
  // [[Page Name|Alias]] -> [Alias](hop://Page Name)
  const processedContent = content.replace(/\[\[([^\]]+)\]\]/g, (match, inner) => {
    if (inner.includes('|')) {
      const parts = inner.split('|');
      const alias = parts.pop();
      const link = parts.join('|'); // In case link has pipes (rare, but just in case)
      return `[${alias}](${/^https?:\/\//i.test(link) ? link : `hop://${link}`})`;
    }
    return `[${inner}](${/^https?:\/\//i.test(inner) ? inner : `hop://${inner}`})`;
  });

  return (
    <div 
      className="markdown-body font-sans text-white/85 selection:bg-accent/30 selection:text-white"
      onClick={handleContainerClick}
    >
      <div role="status" aria-live="polite" className="text-xs text-[#00d4ff]">{saveMessage}</div>
      <ReactMarkdown 
        remarkPlugins={[remarkGfm]} 
        rehypePlugins={[rehypeRaw]}
        components={components}
        urlTransform={(value) => value}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  );
}
