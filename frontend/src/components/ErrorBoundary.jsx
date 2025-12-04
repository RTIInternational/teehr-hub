import React from 'react';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // Log the error details
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="d-flex flex-column justify-content-center align-items-center h-100 bg-light">
          <div className="text-center p-4">
            <i className="bi bi-exclamation-triangle text-warning fs-1 mb-3"></i>
            <h5 className="text-muted mb-3">Component Error</h5>
            <p className="text-muted mb-4">
              {this.state.error?.message || 'Something went wrong with the map component.'}
            </p>
            <button 
              className="btn btn-primary" 
              onClick={this.handleRetry}
            >
              <i className="bi bi-arrow-clockwise me-2"></i>
              Try Again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;