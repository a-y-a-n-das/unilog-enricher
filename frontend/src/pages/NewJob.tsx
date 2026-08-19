import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/Card';
import { FileDropzone } from '../components/upload/FileDropzone';
import { AlertCircle, CheckCircle, Loader2 } from 'lucide-react';
import { jobsApi, isApiError } from '../api/jobs';
import { ResearchCapacityCard } from '../components/upload/ResearchCapacityCard';

export function NewJob() {
  const navigate = useNavigate();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!selectedFile || uploading) return;

    setUploading(true);
    setError(null);

    try {
      const response = await jobsApi.createJob(selectedFile);
      navigate(`/jobs/${response.job_id}`);
    } catch (err) {
      if (isApiError(err)) {
        setError(err.detail);
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
    } finally {
      setUploading(false);
    }
  };

  const handleFileSelect = (file: File | null) => {
    setSelectedFile(file);
    if (file) setError(null);
  };

  const isXlsx = selectedFile?.name.toLowerCase().endsWith('.xlsx');

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-display text-unilog-text">New Enrichment Job</h1>
        <p className="mt-2 text-body text-unilog-textMuted">
          Upload your Excel workbook or CSV file to start the enrichment pipeline.
        </p>
      </div>

      <Card variant="elevated">
        <CardHeader>
          <CardTitle>Upload Excel Workbook or CSV</CardTitle>
          <CardDescription>
            Drag and drop or click to browse. Maximum file size: 10MB.
            {isXlsx && ' Excel workbooks must contain a sheet named "Input".'}
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-0">
          <FileDropzone
            onFileSelect={handleFileSelect}
            disabled={uploading}
          />

          {error && (
            <div className="mt-4 p-3 bg-unilog-errorSoft border border-unilog-error/20 rounded-lg flex items-start gap-3" role="alert">
              <AlertCircle className="h-5 w-5 text-unilog-error flex-shrink-0 mt-0.5" />
              <p className="text-body-sm text-unilog-error">{error}</p>
            </div>
          )}

          <div className="mt-6 flex justify-end">
            <Button
              size="lg"
              onClick={handleSubmit}
              disabled={!selectedFile || uploading}
              loading={uploading}
            >
              {uploading ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Creating Job&hellip;
                </>
              ) : (
                <>
                  <CheckCircle className="h-5 w-5" />
                  Start Enrichment
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>File Requirements</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <ul className="space-y-2 text-body-sm text-unilog-textMuted">
            <li className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-unilog-success flex-shrink-0" />
              <span>Excel workbook (.xlsx) or CSV (.csv)</span>
            </li>
            {isXlsx && (
              <>
                <li className="flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-unilog-success flex-shrink-0" />
                  {/* eslint-disable-next-line react/no-unescaped-entities */}
                  <span>Must contain a sheet named exactly "Input" (case-sensitive)</span>
                </li>
                <li className="flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-unilog-success flex-shrink-0" />
                  {/* eslint-disable-next-line react/no-unescaped-entities */}
                  <span>First row of the "Input" sheet should contain column headers</span>
                </li>
              </>
            )}
            {selectedFile && selectedFile.name.toLowerCase().endsWith('.csv') && (
              <li className="flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-unilog-success flex-shrink-0" />
                <span>First row should contain column headers</span>
              </li>
            )}
            <li className="flex items-center gap-2">
              <CheckCircle className="h-4 w-4 text-unilog-success flex-shrink-0" />
              <span>Maximum 10MB file size</span>
            </li>
          </ul>
        </CardContent>
      </Card>

      <ResearchCapacityCard />
    </div>
  );
}