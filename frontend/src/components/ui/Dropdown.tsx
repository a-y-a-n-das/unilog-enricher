import { useState, useRef, useEffect, ReactNode } from 'react';
import { cn } from '../../lib/utils';
import { ChevronDown } from 'lucide-react';

export interface DropdownProps {
  trigger: ReactNode;
  content: ReactNode;
  align?: 'left' | 'right';
}

export function Dropdown({ trigger, content, align = 'left' }: DropdownProps) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (triggerRef.current && !triggerRef.current.contains(event.target as Node)) {
        if (contentRef.current && !contentRef.current.contains(event.target as Node)) {
          setOpen(false);
        }
      }
    }

    if (open) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener('keydown', handleEscape);
    }
    return () => document.removeEventListener('keydown', handleEscape);
  }, [open]);

  return (
    <div className="relative inline-block" ref={triggerRef}>
      <div onClick={() => setOpen(!open)} className="cursor-pointer">
        {trigger}
      </div>
      {open && (
        <div
          ref={contentRef}
          className={cn(
            'fixed z-50 mt-1.5 min-w-[280px] max-w-[480px] bg-unilog-bgElevated border border-unilog-border rounded-lg shadow-elevated p-3 animate-in fade-in-0 zoom-in-95 duration-fast',
            align === 'right' ? 'right-0' : 'left-0'
          )}
        >
          {content}
        </div>
      )}
    </div>
  );
}

export interface TruncatedTextProps {
  text: string;
  maxLength?: number;
  tooltip?: string;
}

export function TruncatedText({ text, maxLength = 80, tooltip }: TruncatedTextProps) {
  const [expanded, setExpanded] = useState(false);
  const isTruncated = text.length > maxLength;
  const displayText = expanded || !isTruncated ? text : text.slice(0, maxLength) + '…';

  if (!isTruncated) {
    return <span className="font-mono text-body-sm">{text}</span>;
  }

  return (
    <Dropdown
      trigger={
        <span className="font-mono text-body-sm cursor-help" title={tooltip || 'Click to expand'}>
          {displayText}
          {!expanded && <ChevronDown className="inline-block ml-1 h-3 w-3 text-unilog-textMuted" />}
        </span>
      }
      content={
        <div className="font-mono text-body-sm whitespace-pre-wrap max-h-[300px] overflow-y-auto">
          {text}
          <div className="mt-2 pt-2 border-t border-unilog-border flex justify-end">
            <button
              onClick={() => setExpanded(false)}
              className="text-caption text-unilog-accent hover:underline"
            >
              Show less
            </button>
          </div>
        </div>
      }
      align="left"
    />
  );
}