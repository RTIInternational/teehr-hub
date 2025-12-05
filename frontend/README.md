# TEEHR Dashboard - React Frontend

This is the React frontend for the TEEHR Dashboard, a hydrological data visualization application built with Vite, MapLibre GL JS, and Plotly.js.

## Technologies Used

- **React 19** - Frontend framework
- **Vite** - Fast build tool and development server
- **MapLibre GL JS** - Interactive mapping
- **Plotly.js** - Data visualization and charting
- **Bootstrap 5** - UI components and styling

## Available Scripts

In the project directory, you can run:

### `npm run dev` or `npm start`

Runs the app in development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in your browser.

The page will reload instantly when you make changes thanks to Vite's Hot Module Replacement (HMR).\
You may also see any lint errors in the console.

### `npm run build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance using Vite's fast bundling.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

### `npm run preview`

Serves the production build locally for testing.\
Useful for testing the production build before deployment.

## Project Structure

```
src/
├── components/          # React components
│   ├── Dashboard.jsx    # Main dashboard layout
│   ├── MapComponent.jsx # Interactive map with MapLibre
│   ├── Navbar.jsx       # Navigation bar
│   ├── PlotlyChart.jsx  # Timeseries charts
│   └── ...
├── context/             # React context for state management
│   └── DashboardContext.jsx
├── hooks/               # Custom React hooks
│   └── useDataFetching.js
├── services/            # API service layer
│   └── api.js
└── App.jsx              # Main app component
```

## Environment Variables

Create a `.env` file in the project root to configure the API endpoint:

```
VITE_API_URL=http://localhost:8000
```

Note: Environment variables must be prefixed with `VITE_` to be accessible in the client.

## Backend Integration

This frontend connects to a FastAPI backend running on port 8000. The Vite development server is configured to proxy API requests to the backend:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API endpoints are proxied from `/api/*` to the backend

## Features

- **Interactive Map**: MapLibre GL JS powered map showing USGS gauge locations
- **Timeseries Visualization**: Plotly.js charts for hydrological data
- **Real-time Data**: Connect to TEEHR database via FastAPI backend
- **Responsive Design**: Bootstrap-based responsive UI
- **Fast Development**: Vite's instant HMR for rapid development

## Getting Started

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start the development server:
   ```bash
   npm run dev
   ```

3. Make sure the FastAPI backend is running on port 8000

4. Open http://localhost:3000 to view the dashboard

## Learn More

- [Vite Documentation](https://vitejs.dev/)
- [React Documentation](https://reactjs.org/)
- [MapLibre GL JS](https://maplibre.org/)
- [Plotly.js](https://plotly.com/javascript/)
- [Bootstrap 5](https://getbootstrap.com/)
