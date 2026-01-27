import React, { useState, useRef, useEffect } from 'react';

// Example using Bootstrap CSS classes directly
const BootstrapNativeDropdown = ({ columnIndex, uniqueValues, selectedValues, onFilterChange }) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const clearAll = () => {
    selectedValues.forEach(value => {
      onFilterChange(columnIndex, value, false);
    });
  };

  return (
    <div className="dropdown w-100" ref={dropdownRef}>
      <button
        className="btn btn-outline-secondary btn-sm dropdown-toggle w-100 d-flex justify-content-between align-items-center"
        type="button"
        style={{ fontSize: '13px' }}
        onClick={() => setIsOpen(!isOpen)}
      >
        <span>{selectedValues.length === 0 ? 'All' : `${selectedValues.length} selected`}</span>
      </button>

      {isOpen && (
        <ul 
          className="dropdown-menu show position-absolute"
          style={{ 
            minWidth: '200px',
            maxHeight: '200px', 
            overflowY: 'auto',
            fontSize: '12px',
            zIndex: 1050 // Bootstrap's dropdown z-index
          }}
        >
          <li>
            <div className="dropdown-header d-flex justify-content-between">
              <button
                className="btn btn-sm btn-link p-0 text-decoration-none"
                style={{ fontSize: '13px' }}
                onClick={clearAll}
              >
                Clear All
              </button>
            </div>
          </li>
          
          <li><hr className="dropdown-divider" /></li>
          
          {uniqueValues.map(value => (
            <li key={value}>
              <div className="dropdown-item-text px-3 py-2">
                <div className="form-check mb-0">
                  <input
                    className="form-check-input"
                    type="checkbox"
                    id={`filter-${columnIndex}-${value}`}
                    checked={selectedValues.includes(value)}
                    onChange={(e) => onFilterChange(columnIndex, value, e.target.checked)}
                  />
                  <label 
                    className="form-check-label flex-grow-1" 
                    htmlFor={`filter-${columnIndex}-${value}`}
                    style={{ fontSize: '14px' }}
                  >
                    {value}
                  </label>
                </div>
              </div>
            </li>
          ))}
          
          {uniqueValues.length === 0 && (
            <li><span className="dropdown-item-text text-muted">No values available</span></li>
          )}
        </ul>
      )}
    </div>
  );
};

export default BootstrapNativeDropdown;