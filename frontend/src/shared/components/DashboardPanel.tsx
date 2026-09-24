type DashboardPanelProps = {
  header?: React.ReactNode | null;
  className?: string;
  style?: React.CSSProperties;
  headerStyle?: React.CSSProperties;
  bodyClassName?: string;
  bodyStyle?: React.CSSProperties;
};

export const DashboardPanel = ({
  children,
  header = null,
  className = '',
  style = {},
  headerStyle = {},
  bodyClassName = '',
  bodyStyle = {},
}: React.PropsWithChildren<DashboardPanelProps>) => {
  return (
    <div
      className={className}
      style={{
        display: 'flex',
        flexDirection: 'column',
        minHeight: 0,
        height: '100%',
        border: '1px solid #dee2e6',
        borderRadius: '8px',
        overflow: 'hidden',
        background: '#fff',
        ...style,
      }}
    >
      {header !== null && (
        <div
          style={{
            flex: '0 0 auto',
            minHeight: 0,
            borderBottom: '1px solid #dee2e6',
            background: '#f8f9fa',
            padding: '10px 12px',
            ...headerStyle,
          }}
        >
          {header}
        </div>
      )}

      <div
        className={bodyClassName}
        style={{
          flex: '1 1 auto',
          minHeight: 0,
          overflow: 'hidden',
          padding: '12px',
          ...bodyStyle,
        }}
      >
        {children}
      </div>
    </div>
  );
};

export default DashboardPanel;
