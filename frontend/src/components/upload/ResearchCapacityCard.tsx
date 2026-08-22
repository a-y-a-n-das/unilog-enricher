import { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/Card';
import { Loader2, Info, AlertCircle } from 'lucide-react';
import { jobsApi } from '../../api/jobs';
import type { CreditsResponse } from '../../types/api';

const POLL_INTERVAL = 15000;

export function ResearchCapacityCard() {
  const [credits, setCredits] = useState<CreditsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCredits = useCallback(async () => {
    try {
      setError(null);
      const data = await jobsApi.getCredits();
      setCredits(data);
    } catch (err) {
      console.warn('Failed to fetch credits:', err);
      setError('Credits unavailable');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCredits();
    const interval = setInterval(fetchCredits, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchCredits]);

  if (!loading && error && !credits) {
    return (
      <Card variant="elevated" className="border-unilog-border/50">
        <CardContent className="pt-0 pb-4 px-4">
          <div className="flex items-center gap-2 text-body-sm text-unilog-textMuted">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <span>Free credits unavailable</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!credits) {
    return (
      <Card variant="elevated" className="border-unilog-border/50">
        <CardContent className="pt-0 pb-4 px-4">
          <div className="flex items-center gap-2 text-body-sm text-unilog-textMuted">
            <Loader2 className="h-4 w-4 animate-spin flex-shrink-0" />
            <span>Loading free credits...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  const { remaining_credits, initial_credits, credits_used_this_session, note } = credits;

  return (
    <Card variant="elevated" className="border-unilog-border/50">
      <CardHeader className="pb-2">
        <CardTitle className="text-body flex items-center gap-2">
          <Info className="h-5 w-5 text-unilog-primary" />
          Free Credits
        </CardTitle>
        <CardDescription className="text-body-xs">
          Each attempted row consumes 1 credit. This is an application-level allowance, not related to Exa API billing.
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-0 space-y-3">
        <div className="grid grid-cols-2 gap-4">
          <div className="p-3 bg-unilog-bgSoft/50 rounded-lg">
            <p className="text-body-xs text-unilog-textMuted">Credits Used (Session)</p>
            <p className="text-display font-mono text-unilog-text">{credits_used_this_session}</p>
          </div>
          <div className="p-3 bg-unilog-bgSoft/50 rounded-lg">
            <p className="text-body-xs text-unilog-textMuted">Initial Credits</p>
            <p className="text-display font-mono text-unilog-text">{initial_credits}</p>
          </div>
        </div>

        <div className={`p-3 rounded-lg ${
          remaining_credits === 0
            ? 'bg-unilog-destructive/10 border border-unilog-destructive/20'
            : 'bg-unilog-primary/5 border border-unilog-primary/20'
        }`}>
          <p className="text-body-xs text-unilog-textMuted">Free Credits Remaining</p>
          <p className={`text-2xl font-bold font-mono ${
            remaining_credits === 0 ? 'text-unilog-destructive' : 'text-unilog-primary'
          }`}>
            {remaining_credits}
          </p>
          <p className="text-body-xs text-unilog-textMuted/70 mt-1">
            {remaining_credits === 1 ? '1 free row remaining' : `${remaining_credits} free rows remaining`}
          </p>
        </div>

        <p className="text-body-xs text-unilog-textMuted/70 text-center">{note}</p>
      </CardContent>
    </Card>
  );
}