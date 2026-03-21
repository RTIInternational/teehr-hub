import { useState, useRef, useEffect } from 'react';
import { Form } from 'react-bootstrap';

/**
 * A clean multi-select dropdown component
 * Handles all the event propagation issues internally
 */
const MultiSelectDropdown = ({
  options = [],
  selected = [],
  onChange,
  placeholder = 'Select...',
  allSelectedText = 'All selected',
  noneSelectedText = 'None selected',
  style = {}
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const handleToggle = (value) => {
    const newSelected = selected.includes(value)
      ? selected.filter(v => v !== value)
      : [...selected, value];
    onChange(newSelected);
  };

  const handleSelectAll = () => {
    onChange([...options]);
  };

  const handleClearAll = () => {
    onChange([]);
  };

  const getDisplayText = () => {
    if (selected.length === 0) return noneSelectedText;
    if (selected.length === options.length) return allSelectedText;
    return `${selected.length} of ${options.length} selected`;
  };

  return (
    <div ref={containerRef} className="multi-select-dropdown" style={{ position: 'relative', ...style }}>
      {/* Toggle Button */}
      <button
        type="button"
        className="btn btn-outline-secondary w-100 d-flex justify-content-between align-items-center"
        onClick={() => setIsOpen(!isOpen)}
        style={{ fontSize: '14px' }}
      >
        <span className="text-truncate">{getDisplayText()}</span>
        <span style={{ marginLeft: '8px' }}>{isOpen ? '▲' : '▼'}</span>
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          className="multi-select-menu"
          style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            zIndex: 1050,
            backgroundColor: 'white',
            border: '1px solid #dee2e6',
            borderRadius: '4px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            marginTop: '2px',
            minWidth: '250px'
          }}
        >
          {/* Header with Select All / Clear All */}
          <div className="px-3 py-2 border-bottom d-flex gap-3" style={{ backgroundColor: '#f8f9fa' }}>
            <button
              type="button"
              className="btn btn-sm btn-link p-0 text-decoration-none"
              onClick={handleSelectAll}
            >
              Select All
            </button>
            <button
              type="button"
              className="btn btn-sm btn-link p-0 text-decoration-none text-danger"
              onClick={handleClearAll}
            >
              Clear All
            </button>
          </div>

          {/* Options List */}
          <div style={{ maxHeight: '250px', overflowY: 'auto' }}>
            {options.map((option) => (
              <div
                key={option}
                className="px-3 py-2 multi-select-option"
                style={{ cursor: 'pointer' }}
                onClick={() => handleToggle(option)}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f8f9fa'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
              >
                <Form.Check
                  type="checkbox"
                  id={`multi-select-${option}`}
                  label={option}
                  checked={selected.includes(option)}
                  onChange={() => {}} // Handled by parent div onClick
                  className="mb-0"
                  style={{ pointerEvents: 'none' }}
                />
              </div>
            ))}
            {options.length === 0 && (
              <div className="px-3 py-2 text-muted">No options available</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default MultiSelectDropdown;
