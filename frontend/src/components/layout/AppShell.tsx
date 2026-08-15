import { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { cn } from '../../lib/utils';
import { Sidebar } from './Sidebar';
import { SystemStatus } from './SystemStatus';
import { Menu } from 'lucide-react';
import { useHealthCheck } from '../../hooks/useHealthCheck';

export function AppShell() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const { healthStatus } = useHealthCheck();

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth >= 1024) {
        setMobileMenuOpen(false);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <div className="min-h-screen bg-unilog-bg text-unilog-text">
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      <div
        className={cn(
          'transition-all duration-300 ease-out-quart min-h-screen flex flex-col',
          sidebarCollapsed ? 'lg:pl-16' : 'lg:pl-64'
        )}
      >
        <header className="sticky top-0 z-30 h-16 bg-unilog-bg/80 backdrop-blur-sm border-b border-unilog-border flex items-center justify-between px-4 lg:px-6">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="lg:hidden p-2 rounded-lg text-unilog-textMuted hover:text-unilog-text hover:bg-unilog-bgElevated"
              aria-label="Open menu"
              aria-expanded={mobileMenuOpen}
            >
              <Menu className="h-6 w-6" />
            </button>
            <h1 className="text-h2 font-semibold text-unilog-text hidden sm:block">UniLog Enricher</h1>
          </div>

          <div className="flex items-center gap-4">
            <SystemStatus status={healthStatus} />
          </div>
        </header>

        <main className="flex-1 p-4 lg:p-6 overflow-auto">
          <Outlet />
        </main>
      </div>

      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-50 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
          aria-hidden="true"
        >
          <div
            className="absolute inset-0 bg-black/50 animate-in fade-in"
            onClick={(e) => e.stopPropagation()}
          />
          <Sidebar
            collapsed={false}
            onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="absolute left-0 top-0 h-full w-64 bg-unilog-bg border-r border-unilog-border shadow-elevated animate-in slide-in-from-left"
          />
        </div>
      )}
    </div>
  );
}