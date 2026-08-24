const defaultWrapperStyle = {
  overflowY: 'auto',
  flex: 1,
};

const defaultTableStyle = {
  fontSize: '0.82rem',
};

const mergeClassNames = (...classes) => classes.filter(Boolean).join(' ');

const SharedDataTable = ({
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
}) => {
  const resolveHeaderKey = (header, headerIndex) => {
    if (getHeaderKey) return getHeaderKey(header, headerIndex);
    if (header && typeof header === 'object' && header.key) return header.key;
    return headerIndex;
  };

  const resolveRowKey = (row, rowIndex) => {
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
                  const cellProps = getCellProps ? getCellProps(row, header, rowIndex, headerIndex) || {} : {};
                  const { className: cellClassName, ...restCellProps } = cellProps;

                  return (
                    <td
                      key={`${resolveHeaderKey(header, headerIndex)}-${rowIndex}`}
                      className={cellClassName}
                      {...restCellProps}
                    >
                      {renderCell
                        ? renderCell(row, header, rowIndex, headerIndex)
                        : row?.[header]}
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
