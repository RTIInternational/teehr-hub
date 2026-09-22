# TEEHR Dashboard - React Frontend

This is the React frontend for the TEEHR Dashboard, a hydrological data visualization application built with Vite, MapLibre GL JS, and Plotly.js.

## Technologies Used

- **React 19** - Frontend framework
- **TypeScript 7** - Primary application language for the frontend codebase
- **TanStack Query** - Server-state fetching and caching
- **Vite** - Fast build tool and development server
- **MapLibre GL JS** - Interactive mapping
- **Plotly.js** - Data visualization and charting
- **Bootstrap 5** - UI components and styling
- **Oxlint + oxfmt** - Linting and formatting toolchain

## Available Scripts

In the project directory, you can run:

### `npm run dev` or `npm start`

Runs the app in development mode.\
Open [http://localhost:8080](http://localhost:8080) to view it in your browser.

The page will reload instantly when you make changes thanks to Vite's Hot Module Replacement (HMR).\
You may also see any lint errors in the console.

### `npm run build`

Builds the app for production to the `build` folder.\
This runs the TypeScript build check first and then creates the production bundle with Vite.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

### `npm run preview`

Serves the production build locally for testing.\
Useful for testing the production build before deployment.

### `npm run lint` and `npm run lint:fix`

Runs oxlint across the frontend codebase.

### `npm run format:check` and `npm run format:fix`

Runs oxfmt across the frontend source and style files.

## Project Structure

```
src/
├── features/
│   ├── auth/                      # Auth provider and auth hooks
│   ├── forecast/                  # Forecast dashboard feature
│   ├── nwmd/                      # NWMD dashboard feature
│   ├── retrospective/             # Retrospective dashboard feature
│   └── data_management/           # Data management dashboard feature
├── shared/
│   ├── components/                # Reusable components
│   ├── hooks/                     # Shared hooks
│   ├── queries/                   # Shared TanStack Query hooks
│   ├── types/                     # Shared TypeScript types
│   └── utils/                     # Shared utilities
├── config/                        # Frontend configuration
├── pages/                         # Route-level pages (e.g., admin)
├── services/                      # API service layer
├── App.tsx                        # Main app component
└── index.tsx                      # Application entry point and QueryClientProvider
```

## Environment Variables

Create a `.env` file in the project root to configure the API endpoint and external service URLs:

```
VITE_API_BASE_URL=http://localhost:8000
VITE_KEYCLOAK_URL=https://auth.teehr.local.app.garden
VITE_PREFECT_URL=https://prefect.teehr.local.app.garden
VITE_JUPYTERHUB_URL=https://hub.teehr.local.app.garden/hub/spawn
```

Note: Environment variables must be prefixed with `VITE_` to be accessible in the client.

## Backend Integration

This frontend connects to a FastAPI backend. The Vite development server proxies API requests to the backend:

- Frontend: http://localhost:8080
- Backend API: configured by `VITE_API_BASE_URL` or defaults to `http://127.0.0.1:8000`
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

3. Optionally run lint and format checks during development:
   ```bash
   npm run lint
   npm run format:check
   ```

4. Make sure the API backend is reachable through `VITE_API_BASE_URL` or the default local Garden URL

5. Open http://localhost:8080 to view the dashboard

## Development Guidance

- Prefer `.ts` and `.tsx` for all new modules and components.
- Use TanStack Query for server-state fetching and caching.
- Place new dashboard code under `src/features/<feature-name>/` whenever practical.
- Do not add new first-party JavaScript source files to this repo.
- Run `npm run lint`, `npm run format:check`, and `npm run build` before merging substantial frontend changes.

## Learn More

- [Vite Documentation](https://vitejs.dev/)
- [React Documentation](https://reactjs.org/)
- [MapLibre GL JS](https://maplibre.org/)
- [Plotly.js](https://plotly.com/javascript/)
- [Bootstrap 5](https://getbootstrap.com/)
