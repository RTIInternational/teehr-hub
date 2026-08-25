import type React from 'react';

const defaultWrapperStyle: React.CSSProperties = {
  overflowY: 'auto',
  flex: 1,
};

const defaultTableStyle: React.CSSProperties = {
  fontSize: '0.82rem',
};

const mergeClassNames = (...classes: Array<string | undefined | null | false>) =>
  classes.filter(Boolean).join(' ');

type HeaderWithKey = {
  key: React.Key;
};

type SharedDataTableProps<TRow = Record<string, unknown>, THeader = string> = {
  headers?: THeader[];
  rows?: TRow[];
  wrapperClassName?: string;
  wrapperStyle?: React.CSSProperties;
  tableClassName?: string;
  tableStyle?: React.CSSProperties;
  theadClassName?: string;
  getHeaderKey?: (header: THeader, headerIndex: number) => React.Key;
  renderHeaderCell?: (header: THeader, headerIndex: number) => React.ReactNode;
  getHeaderProps?: (
    header: THeader,
    headerIndex: number
  ) => React.ThHTMLAttributes<HTMLTableCellElement>;
  getRowKey?: (row: TRow, rowIndex: number) => React.Key;
  getRowProps?: (row: TRow, rowIndex: number) => React.HTMLAttributes<HTMLTableRowElement>;
  getRowClassName?: (row: TRow, rowIndex: number) => string | undefined;
  renderCell?: (
    row: TRow,
    header: THeader,
    rowIndex: number,
    headerIndex: number
  ) => React.ReactNode;
  getCellProps?: (
    row: TRow,
    header: THeader,
    rowIndex: number,
    headerIndex: number
  ) => React.TdHTMLAttributes<HTMLTableCellElement>;
};

const hasKey = (header: unknown): header is HeaderWithKey => {
  return typeof header === 'object' && header !== null && 'key' in header;
};

const resolveDefaultCellValue = <TRow, THeader>(
  row: TRow,
  header: THeader,
  headerIndex: number
): unknown => {
  if (Array.isArray(row)) {
    return row[headerIndex];
  }

  if (row && typeof row === 'object') {
    const headerKey =
      typeof header === 'number' || typeof header === 'string' ? header : headerIndex;
    return (row as Record<string, unknown>)[String(headerKey)];
  }

  return undefined;
};

const SharedDataTable = <TRow, THeader>({
  headers = [],
  rows = [],
  wrapperClassName = '',
  wrapperStyle = defaultWrapperStyle,
  tableClassName = 'table table-sm table-bordered table-hover mb-0',
  tableStyle = defaultTableStyle,
  theadClassName = 'table-light sticky-top',
  getHeaderKey,
  renderHeaderCell,
  getHeaderProps,
  getRowKey,
  getRowProps,
  getRowClassName,
  renderCell,
  getCellProps,
}: SharedDataTableProps<TRow, THeader>) => {
  const resolveHeaderKey = (header: THeader, headerIndex: number): React.Key => {
    if (getHeaderKey) return getHeaderKey(header, headerIndex);
    if (hasKey(header)) return header.key;
    return headerIndex;
  };

  const resolveRowKey = (row: TRow, rowIndex: number): React.Key => {
    if (getRowKey) return getRowKey(row, rowIndex);
    return rowIndex;
  };

  return (
    <div className={wrapperClassName} style={wrapperStyle}>
      <table className={tableClassName} style={tableStyle}>
        <thead className={theadClassName}>
          <tr>
            {headers.map((header, headerIndex) => {
              const headerProps = getHeaderProps ? getHeaderProps(header, headerIndex) || {} : {};
              const { className, ...restHeaderProps } = headerProps;

              return (
                <th
                  key={resolveHeaderKey(header, headerIndex)}
                  className={className}
                  {...restHeaderProps}
                >
                  {renderHeaderCell ? renderHeaderCell(header, headerIndex) : String(header)}
                </th>
              );
            })}
          </tr>
        </thead>

        <tbody>
          {rows.map((row, rowIndex) => {
            const rowProps = getRowProps ? getRowProps(row, rowIndex) || {} : {};
            const rowClassName = getRowClassName ? getRowClassName(row, rowIndex) : '';
            const { className, ...restRowProps } = rowProps;

            return (
              <tr
                key={resolveRowKey(row, rowIndex)}
                className={mergeClassNames(className, rowClassName)}
                {...restRowProps}
              >
                {headers.map((header, headerIndex) => {
                  const cellProps = getCellProps
                    ? getCellProps(row, header, rowIndex, headerIndex) || {}
                    : {};
                  const { className: cellClassName, ...restCellProps } = cellProps;

                  return (
                    <td
                      key={`${resolveHeaderKey(header, headerIndex)}-${rowIndex}`}
                      className={cellClassName}
                      {...restCellProps}
                    >
                      {renderCell
                        ? renderCell(row, header, rowIndex, headerIndex)
                        : String(resolveDefaultCellValue(row, header, headerIndex) ?? '')}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default SharedDataTable;
