import { NavLink, useLocation } from 'react-router-dom';
import { cn } from '../../lib/utils';
import { LayoutDashboard, PlusCircle, ListChecks, ChevronLeft, ChevronRight } from 'lucide-react';

interface NavItem {
  path: string;
  label: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  { path: '/', label: 'Dashboard', icon: <LayoutDashboard className="h-5 w-5" /> },
  { path: '/new', label: 'New Job', icon: <PlusCircle className="h-5 w-5" /> },
  { path: '/jobs', label: 'Jobs', icon: <ListChecks className="h-5 w-5" /> },
];

export interface SidebarProps {
  collapsed?: boolean;
  onToggle?: () => void;
  className?: string;
}

export function Sidebar({ collapsed = false, onToggle, className }: SidebarProps) {
  const location = useLocation();

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 h-full bg-unilog-bg border-r border-unilog-border transition-all duration-300 ease-out-quart flex flex-col',
        collapsed ? 'w-16' : 'w-64',
        className
      )}
      aria-label="Main navigation"
    >
      <div className="flex h-16 items-center justify-between px-4 border-b border-unilog-border">
        {!collapsed && (
          <NavLink to="/" className="flex items-center gap-2" aria-label="UniLog Enricher Home">
            <div className="p-1.5 bg-unilog-accent rounded-lg">
              <svg className="h-5 w-5 text-unilog-bg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M8 12h8M8 16h5M8 20h3" strokeLinecap="round" />
                <circle cx="19" cy="20" r="3" fill="currentColor" />
              </svg>
            </div>
            <span className="text-h3 font-semibold text-unilog-text">UniLog</span>
          </NavLink>
        )}
        {collapsed && (
          <NavLink to="/" className="p-2" aria-label="UniLog Enricher Home">
            <div className="p-1.5 bg-unilog-accent rounded-lg">
              <svg className="h-5 w-5 text-unilog-bg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M8 12h8M8 16h5M8 20h3" strokeLinecap="round" />
                <circle cx="19" cy="20" r="3" fill="currentColor" />
              </svg>
            </div>
          </NavLink>
        )}
        <button
          onClick={onToggle}
          className={cn(
            'p-1.5 rounded-lg text-unilog-textMuted hover:text-unilog-text hover:bg-unilog-bgElevated transition-colors',
            collapsed && 'rotate-180'
          )}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-expanded={!collapsed}
        >
          {collapsed ? <ChevronRight className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
        </button>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto" aria-label="Navigation">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path));
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive: active }) => cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors duration-fast',
                'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-unilog-accent focus-visible:ring-offset-2 focus-visible:ring-offset-unilog-bg',
                active
                  ? 'bg-unilog-accentSoft text-unilog-accent'
                  : 'text-unilog-textMuted hover:text-unilog-text hover:bg-unilog-bgElevated',
                collapsed && 'justify-center'
              )}
              title={collapsed ? item.label : undefined}
              aria-current={isActive ? 'page' : undefined}
            >
              <span className="flex-shrink-0">{item.icon}</span>
              {!collapsed && <span className="text-body-sm font-medium">{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>

      <div className="p-3 border-t border-unilog-border">
        {!collapsed && (
          <div className="text-caption text-unilog-textMuted text-center">
            UniLog Enricher v1.0
          </div>
        )}
      </div>
    </aside>
  );
}