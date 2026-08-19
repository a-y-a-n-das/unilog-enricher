import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/Card';
import { Loader2, Info } from 'lucide-react';
import { jobsApi } from '../../api/jobs';
import type { TavilyUsageResponse } from '../../types/api';

export function ResearchCapacityCard() {
  const [usage, setUsage] = useState<TavilyUsageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchUsage = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await jobsApi.getTavilyUsage();
      setUsage(data);
    } catch (err) {
      // Silently fail - this is informational only
      console.warn('Failed to fetch Tavily usage:', err);
      setError('Research capacity unavailable');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsage();
  }, []);

  if (!loading && error && !usage) {
    return (
      <Card variant="elevated" className="border-unilog-border/50">
        <CardContent className="pt-0 pb-4 px-4">
          <div className="flex items-center gap-2 text-body-sm text-unilog-textMuted">
            <Info className="h-4 w-4 flex-shrink-0" />
            <span>Research capacity unavailable</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!usage) {
    return (
      <Card variant="elevated" className="border-unilog-border/50">
        <CardContent className="pt-0 pb-4 px-4">
          <div className="flex items-center gap-2 text-body-sm text-unilog-textMuted">
            <Loader2 className="h-4 w-4 animate-spin flex-shrink-0" />
            <span>Loading research capacity...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  const { credits_used_this_session, credits_remaining, estimated_credits_per_row, estimated_rows_remaining, monthly_credit_limit, note } = usage;

  // Determine the best estimate for display
  const displayRemaining = credits_remaining ?? (monthly_credit_limit > 0 ? Math.max(0, monthly_credit_limit - (credits_used_this_session ?? 0)) : null);
  const displayRows = estimated_rows_remaining ?? (displayRemaining !== null && estimated_credits_per_row > 0 ? Math.max(0, Math.floor(displayRemaining / estimated_credits_per_row)) : null);

  return (
    <Card variant="elevated" className="border-unilog-border/50">
      <CardHeader className="pb-2">
        <CardTitle className="text-body flex items-center gap-2">
          <Info className="h-5 w-5 text-unilog-primary" />
          Research Capacity
        </CardTitle>
        <CardDescription className="text-body-xs">
          Estimated Tavily API capacity for planning. Does not block processing.
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-0 space-y-3">
        <div className="grid grid-cols-2 gap-4">
          <div className="p-3 bg-unilog-bgSoft/50 rounded-lg">
            <p className="text-body-xs text-unilog-textMuted">Credits Used (Session)</p>
            <p className="text-display font-mono text-unilog-text">{credits_used_this_session ?? 0}</p>
          </div>
          <div className="p-3 bg-unilog-bgSoft/50 rounded-lg">
            <p className="text-body-xs text-unilog-textMuted">Est. Credits/Row</p>
            <p className="text-display font-mono text-unilog-text">~{estimated_credits_per_row}</p>
          </div>
        </div>

        <div className="p-3 bg-unilog-primary/5 border border-unilog-primary/20 rounded-lg">
          <p className="text-body-xs text-unilog-primary/80">Estimated Rows Remaining</p>
          <p className="text-2xl font-bold text-unilog-primary font-mono">
            {displayRows !== null ? displayRows : '—'}
          </p>
          <p className="text-body-xs text-unilog-primary/70 mt-1">
            Based on ~{displayRemaining !== null ? displayRemaining : '?'} credits remaining of {monthly_credit_limit} monthly limit
          </p>
        </div>

        <p className="text-body-xs text-unilog-textMuted/70 text-center">{note}</p>
      </CardContent>
    </Card>
  );
}