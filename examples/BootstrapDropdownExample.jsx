import React, { useState } from 'react';
import { Dropdown, Form } from 'react-bootstrap';

// Example of how to use React Bootstrap Dropdown for filter columns
const FilterDropdown = ({ columnIndex, uniqueValues, selectedValues, onFilterChange }) => {
  const [show, setShow] = useState(false);

  const handleToggle = (isOpen, event, metadata) => {
    if (metadata.source !== 'select') {
      setShow(isOpen);
    }
  };

  const handleCheckboxChange = (value, checked) => {
    onFilterChange(columnIndex, value, checked);
  };

  const clearAll = () => {
    selectedValues.forEach(value => {
      onFilterChange(columnIndex, value, false);
    });
  };

  return (
    <Dropdown 
      show={show} 
      onToggle={handleToggle}
      className="w-100"
    >
      <Dropdown.Toggle 
        variant="outline-secondary" 
        size="sm" 
        className="w-100 d-flex justify-content-between align-items-center"
        style={{ fontSize: '13px' }}
      >
        <span>{selectedValues.length === 0 ? 'All' : `${selectedValues.length} selected`}</span>
      </Dropdown.Toggle>

      <Dropdown.Menu 
        style={{ 
          minWidth: '200px',
          maxHeight: '200px', 
          overflowY: 'auto',
          fontSize: '12px'
        }}
      >
        <Dropdown.Header>
          <button
            className="btn btn-sm btn-link p-0 text-decoration-none"
            style={{ fontSize: '13px' }}
            onClick={(e) => {
              e.preventDefault();
              clearAll();
            }}
          >
            Clear All
          </button>
        </Dropdown.Header>
        
        <Dropdown.Divider />
        
        {uniqueValues.map(value => (
          <Dropdown.Item 
            key={value} 
            as="div" 
            className="p-0"
            onClick={(e) => e.preventDefault()} // Prevent dropdown from closing
          >
            <Form.Check
              type="checkbox"
              id={`filter-${columnIndex}-${value}`}
              label={value}
              checked={selectedValues.includes(value)}
              onChange={(e) => handleCheckboxChange(value, e.target.checked)}
              className="px-3 py-2 mb-0"
              style={{ fontSize: '14px' }}
            />
          </Dropdown.Item>
        ))}
        
        {uniqueValues.length === 0 && (
          <Dropdown.Item disabled>No values available</Dropdown.Item>
        )}
      </Dropdown.Menu>
    </Dropdown>
  );
};

export default FilterDropdown;