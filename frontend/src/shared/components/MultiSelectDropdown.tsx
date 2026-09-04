import React, { useState, useRef, useEffect } from 'react';
import { Form } from 'react-bootstrap';

type MultiSelectDropdownProps = {
  options?: string[];
  selected?: string[];
  onChange: (options: string[]) => void;
  allSelectedText?: string;
  noneSelectedText?: string;
  labelledBy?: string;
  ariaLabel?: string;
  style?: React.CSSProperties;
};

/**
 * A clean multi-select dropdown component
 * Handles all the event propagation issues internally
 */
const MultiSelectDropdown = ({
  options = [],
  selected = [],
  onChange,
  allSelectedText = 'All selected',
  noneSelectedText = 'None selected',
  labelledBy,
  ariaLabel,
  style = {},
}: MultiSelectDropdownProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        event.target instanceof Node &&
        !containerRef.current.contains(event.target)
      ) {
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

  const handleToggle = (value: string) => {
    const newSelected = selected.includes(value)
      ? selected.filter((v) => v !== value)
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
    <div
      ref={containerRef}
      className="multi-select-dropdown"
      style={{ position: 'relative', ...style }}
    >
      {/* Toggle Button */}
      <button
        type="button"
        className="btn btn-outline-secondary w-100 d-flex justify-content-between align-items-center"
        onClick={() => setIsOpen(!isOpen)}
        aria-labelledby={labelledBy}
        aria-label={ariaLabel}
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
            minWidth: '250px',
          }}
        >
          {/* Header with Select All / Clear All */}
          <div
            className="px-3 py-2 border-bottom d-flex gap-3"
            style={{ backgroundColor: '#f8f9fa' }}
          >
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
            {options.map((option) => {
              const inputId = `multi-select-${option}`;
              const checked = selected.includes(option);

              return (
                <label
                  key={option}
                  htmlFor={inputId}
                  className="px-3 py-2 d-flex align-items-center"
                >
                  <Form.Check
                    id={inputId}
                    type="checkbox"
                    checked={checked}
                    onChange={() => handleToggle(option)}
                    label={option}
                    className="mb-0"
                  />
                </label>
              );
            })}
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
