import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { Card, CardContent } from '../components/ui/Card';
import { FileText, ArrowRight, Database, Zap, Shield, PlusCircle } from 'lucide-react';

export function Dashboard() {
  const navigate = useNavigate();

  const handleNewJob = () => {
    navigate('/new');
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <section className="space-y-4">
        <div>
          <h1 className="text-display text-unilog-text">Product Data Enrichment</h1>
          <p className="mt-2 text-body text-unilog-textMuted max-w-2xl">
            Research, enrich and validate product information from Excel workbooks.
          </p>
        </div>

        <Button size="lg" onClick={handleNewJob} className="w-fit">
          <PlusCircle className="h-5 w-5" />
          Start New Job
        </Button>
      </section>

      <section aria-labelledby="how-it-works" className="space-y-4">
        <h2 id="how-it-works" className="text-h3 text-unilog-text">How it works</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <Card variant="elevated">
            <CardContent className="pt-6">
              <div className="p-3 bg-unilog-accentSoft text-unilog-accent rounded-lg w-fit mb-4">
                <FileText className="h-6 w-6" />
              </div>
              <h3 className="text-h3 text-unilog-text mb-2">Upload Excel</h3>
              <p className="text-body-sm text-unilog-textMuted">
                Drag and drop or select your .xlsx workbook. Must contain a sheet named Input.
              </p>
            </CardContent>
          </Card>

          <Card variant="elevated">
            <CardContent className="pt-6">
              <div className="p-3 bg-unilog-successSoft text-unilog-success rounded-lg w-fit mb-4">
                <Zap className="h-6 w-6" />
              </div>
              <h3 className="text-h3 text-unilog-text mb-2">Enrichment Pipeline</h3>
              <p className="text-body-sm text-unilog-textMuted">
                Research, extraction, validation, and resource resolution run automatically per row.
              </p>
            </CardContent>
          </Card>

          <Card variant="elevated">
            <CardContent className="pt-6">
              <div className="p-3 bg-unilog-warningSoft text-unilog-warning rounded-lg w-fit mb-4">
                <Shield className="h-6 w-6" />
              </div>
              <h3 className="text-h3 text-unilog-text mb-2">Download Results</h3>
              <p className="text-body-sm text-unilog-textMuted">
                Get your enriched Excel workbook with all original data plus new validated fields.
              </p>
            </CardContent>
          </Card>
        </div>
      </section>

      <section aria-labelledby="recent-activity" className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 id="recent-activity" className="text-h3 text-unilog-text">Recent Activity</h2>
          <Button variant="ghost" size="sm" onClick={() => navigate('/jobs')}>
            View All <ArrowRight className="h-4 w-4 ml-1" />
          </Button>
        </div>
        <Card>
          <CardContent className="pt-6">
            <div className="text-center py-12">
              <Database className="h-12 w-12 text-unilog-border mx-auto mb-4" />
              <h3 className="text-h3 text-unilog-text mb-2">No enrichment jobs yet</h3>
              <p className="text-body-sm text-unilog-textMuted mb-6 max-w-md mx-auto">
                Upload an Excel workbook to start your first enrichment job. Jobs will appear here once created.
              </p>
              <Button onClick={handleNewJob} size="lg">
                <PlusCircle className="h-5 w-5" />
                Start New Job
              </Button>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}