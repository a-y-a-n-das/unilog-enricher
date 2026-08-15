import { Table } from '../ui/Table';
import { TruncatedText } from '../ui/Dropdown';
import { StatusIndicator } from './StatusIndicator';
import { formatDateTime } from '../../lib/utils';
import type { JobRow } from '../../types/api';

export interface JobRowsTableProps {
  rows: JobRow[];
  loading?: boolean;
}

export function JobRowsTable({ rows, loading = false }: JobRowsTableProps) {
  const columns = [
    {
      key: 'row_number',
      header: 'Row',
      className: 'font-mono tabular-nums',
      width: '80px',
    },
    {
      key: 'status',
      header: 'Status',
      width: '140px',
      render: (row: JobRow) => <StatusIndicator status={row.status} size="sm" />,
    },
    {
      key: 'attempts',
      header: 'Attempts',
      className: 'font-mono tabular-nums text-center',
      width: '100px',
      render: (row: JobRow) => (
        <span className={row.attempts > 1 ? 'text-unilog-warning' : ''}>
          {row.attempts}
        </span>
      ),
    },
    {
      key: 'completed_at',
      header: 'Completed',
      className: 'font-mono',
      width: '180px',
      render: (row: JobRow) => (
        <span className="text-unilog-textMuted">{formatDateTime(row.completed_at)}</span>
      ),
    },
    {
      key: 'error_message',
      header: 'Error',
      className: 'max-w-[300px]',
      render: (row: JobRow) => {
        if (!row.error_message) return <span className="text-unilog-textMuted">—</span>;
        return <TruncatedText text={row.error_message} maxLength={100} tooltip={row.error_message} />;
      },
    },
  ];

  return (
    <Table<JobRow>
      columns={columns}
      data={rows}
      keyExtractor={(row) => String(row.row_number)}
      emptyMessage={loading ? 'Loading rows...' : 'No rows to display'}
      hoverable={!loading}
    />
  );
}