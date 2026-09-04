# TEEHR Dashboard - React Frontend

This is the React frontend for the TEEHR Dashboard, a hydrological data visualization application built with Vite, MapLibre GL JS, and Plotly.js.

## Technologies Used

- **React 19** - Frontend framework
- **TypeScript 7** - Incrementally adopted for new development and ongoing migration
- **TanStack Query** - Server-state fetching and caching for migrated features
- **Vite** - Fast build tool and development server
- **MapLibre GL JS** - Interactive mapping
- **Plotly.js** - Data visualization and charting
- **Bootstrap 5** - UI components and styling
- **Oxlint + oxfmt** - Linting and formatting toolchain

## Migration Status

This frontend is in the middle of an incremental migration across three tracks:

- JavaScript to TypeScript
- React Context based server-state handling to TanStack Query
- Flat component organization to feature-based structure
- ESLint/Prettier to oxlint/oxfmt

Current status:

- **Migrated to TypeScript + TanStack Query + feature-based structure**:
   - Retrospective dashboard and related components/hooks
   - Forecast dashboard and related components/hooks
- **Not yet migrated (still primarily JavaScript + existing context/data-fetching patterns)**:
   - NWMD dashboard and related components/hooks
   - Data management dashboard and related components/hooks

This mixed architecture is expected during the migration window.

Current migration-related configuration:

- TypeScript config lives in `tsconfig.json`, `tsconfig.app.json`, and `tsconfig.node.json`.
- Application source files under `src/` are allowed to remain JavaScript during migration via `allowJs: true`.
- JavaScript files are not type-checked yet via `checkJs: false`.
- Vite config has already been migrated to TypeScript in `vite.config.ts`.
- oxlint is configured to lint both JavaScript and TypeScript files.
- oxfmt is used for formatting JavaScript, TypeScript, and CSS files.

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

Runs oxlint across JavaScript and TypeScript source files.

### `npm run format:check` and `npm run format:fix`

Runs oxfmt across JavaScript, TypeScript, and CSS files.

## Project Structure

```
src/
├── features/
│   ├── auth/                      # Auth provider and auth hooks (TS)
│   ├── forecast/                  # Migrated dashboard feature (TS + TSQ)
│   └── retrospective/             # Migrated dashboard feature (TS + TSQ)
├── shared/
│   ├── components/                # Reusable TS components
│   ├── queries/                   # TanStack Query hooks
│   ├── types/                     # Shared TypeScript types
│   └── utils/                     # Shared utilities
├── components/
│   └── dashboards/
│       ├── data_management/       # Not yet migrated dashboard modules
│       └── nwmd/                  # Not yet migrated dashboard modules
├── context/                       # Existing contexts used by non-migrated areas
├── hooks/                         # Shared hooks (mixed JS/TS during migration)
├── pages/                         # Route-level pages (e.g., admin)
├── services/                      # API service layer
├── App.tsx                        # Main app component
└── index.tsx                      # Application entry point and QueryClientProvider
```

During migration, you will see a mix of `.js`, `.jsx`, `.ts`, and `.tsx` files.

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
- Prefer TanStack Query for new server-state fetching/caching work.
- Place new dashboard code under `src/features/<feature-name>/` whenever practical.
- When modifying older JavaScript-heavy areas, convert nearby files to TypeScript when the added scope remains manageable.
- Keep migration changes incremental and reviewable rather than attempting broad rewrites.
- Run `npm run lint`, `npm run format:check`, and `npm run build` before merging substantial migration work.

## Learn More

- [Vite Documentation](https://vitejs.dev/)
- [React Documentation](https://reactjs.org/)
- [MapLibre GL JS](https://maplibre.org/)
- [Plotly.js](https://plotly.com/javascript/)
- [Bootstrap 5](https://getbootstrap.com/)
