import { useState, useCallback, useRef, DragEvent, ChangeEvent } from 'react';
import { cn } from '../../lib/utils';
import { X, CheckCircle, AlertCircle, FileSpreadsheet, FileText } from 'lucide-react';
import { formatFileSize } from '../../lib/utils';
import * as XLSX from 'xlsx';

const REQUIRED_SHEET = 'Input';

export interface FileDropzoneProps {
  onFileSelect: (file: File | null) => void;
  acceptedTypes?: string[];
  maxSize?: number;
  disabled?: boolean;
  className?: string;
}

export function FileDropzone({
  onFileSelect,
  acceptedTypes = ['.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.csv', 'text/csv', 'application/csv'],
  maxSize = 10 * 1024 * 1024,
  disabled = false,
  className,
}: FileDropzoneProps) {
  const [isDragActive, setIsDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const isXlsxFile = (file: File): boolean => {
    return file.name.toLowerCase().endsWith('.xlsx') || 
           file.type === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
  };

  const validateFile = useCallback(async (file: File): Promise<string | null> => {
    const isValidType = acceptedTypes.some((type) => {
      if (type.startsWith('.')) {
        return file.name.toLowerCase().endsWith(type.toLowerCase());
      }
      return file.type === type || type === '*/*';
    });

    if (!isValidType) {
      return 'Please select an Excel workbook (.xlsx) or CSV file (.csv)';
    }

    if (file.size > maxSize) {
      return `File size must be less than ${formatFileSize(maxSize)}`;
    }

    if (isXlsxFile(file)) {
      try {
        const arrayBuffer = await file.arrayBuffer();
        const workbook = XLSX.read(arrayBuffer, { type: 'array' });

        if (!workbook.SheetNames.includes(REQUIRED_SHEET)) {
          return `The Excel workbook must contain a sheet named "${REQUIRED_SHEET}".`;
        }
      } catch {
        return 'Failed to parse the Excel workbook. Please ensure it is a valid .xlsx file.';
      }
    }

    return null;
  }, [acceptedTypes, maxSize]);

  const handleFileSelect = useCallback(async (file: File | null) => {
    if (!file) {
      setSelectedFile(null);
      setError(null);
      onFileSelect(null);
      return;
    }

    const validationError = await validateFile(file);
    if (validationError) {
      setError(validationError);
      setSelectedFile(null);
      onFileSelect(null);
      return;
    }

    setSelectedFile(file);
    setError(null);
    onFileSelect(file);
  }, [validateFile, onFileSelect]);

  const handleDragEnter = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled) setIsDragActive(true);
  }, [disabled]);

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
  }, []);

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);

    if (disabled) return;

    const file = e.dataTransfer.files[0];
    if (file) {
      handleFileSelect(file);
    }
  }, [disabled, handleFileSelect]);

  const handleClick = useCallback(() => {
    if (!disabled) {
      fileInputRef.current?.click();
    }
  }, [disabled]);

  const handleInputChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    handleFileSelect(file);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, [handleFileSelect]);

  const handleRemoveFile = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    handleFileSelect(null);
  }, [handleFileSelect]);

  const isSelectedXlsx = selectedFile && isXlsxFile(selectedFile);

  return (
    <div className="relative">
      <input
        ref={fileInputRef}
        type="file"
        accept={acceptedTypes.join(',')}
        onChange={handleInputChange}
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
        disabled={disabled}
        aria-label="Upload Excel workbook or CSV file"
      />

      <div
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={handleClick}
        className={cn(
          'relative rounded-xl border-2 transition-all duration-fast',
          'flex flex-col items-center justify-center p-8',
          disabled
            ? 'opacity-50 cursor-not-allowed bg-unilog-bg/50 border-unilog-border'
            : isDragActive
            ? 'border-unilog-accent bg-unilog-accentSoft'
            : 'border-unilog-borderHover hover:border-unilog-accent hover:bg-unilog-bgElevated',
          className
        )}
        role="button"
        tabIndex={disabled ? -1 : 0}
        onKeyDown={(e) => {
          if ((e.key === 'Enter' || e.key === ' ') && !disabled) {
            e.preventDefault();
            handleClick();
          }
        }}
      >
        {selectedFile ? (
          <div className="w-full max-w-md">
            <div className="flex items-center gap-3 p-3 bg-unilog-bg rounded-lg border border-unilog-border">
              <div className="flex-shrink-0 p-2 bg-unilog-successSoft text-unilog-success rounded-lg">
                <CheckCircle className="h-5 w-5" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-body font-medium text-unilog-text truncate">{selectedFile.name}</p>
                <p className="text-caption text-unilog-textMuted">{formatFileSize(selectedFile.size)}</p>
              </div>
              <button
                onClick={handleRemoveFile}
                className="flex-shrink-0 p-1.5 text-unilog-textMuted hover:text-unilog-error transition-colors"
                aria-label="Remove file"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="p-3 bg-unilog-bg rounded-lg border border-unilog-border mb-4">
              {isSelectedXlsx ? (
                <FileSpreadsheet className="h-10 w-10 text-unilog-textMuted mx-auto" />
              ) : (
                <FileText className="h-10 w-10 text-unilog-textMuted mx-auto" />
              )}
            </div>
            <p className="text-h3 text-unilog-text mb-1">Drop Excel workbook or CSV file here</p>
            <p className="text-body-sm text-unilog-textMuted mb-4">or browse files</p>
            <p className="text-caption text-unilog-textMuted">.xlsx and .csv files supported</p>
          </>
        )}
      </div>

      {error && (
        <div className="mt-3 flex items-center gap-2 text-caption text-unilog-error" role="alert">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}