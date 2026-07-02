# Specification: TEEHR-Cloud Welcome Page

## 1. Context & Objectives
- **Goal**: Create a new page that will be the default when visiting https://dashboards.teehr.rtiamanzi.org/.
- **Target URL/Route**: `https://dashboards.teehr.rtiamanzi.org/`
- **Parent Layout**: This page could replace the existing page at `frontend/src/components/common/Home.jsx`, which could in turn be renamed `DashboardsHome.jsx`
- The current url should become `https://dashboards.teehr.rtiamanzi.org/hub`

## 2. Technical Stack
- **React 19** - Frontend framework
- **Vite** - Fast build tool and development server
- **MapLibre GL JS** - Interactive mapping
- **Plotly.js** - Data visualization and charting
- **Bootstrap 5** - UI components and styling

## 3. UI Layout & Component Breakdown
The page styling should be consistent with the current `Home.jsx` page. The main elements of the page will include:
- **Header Section**:
  - Title: "Welcome to TEEHR-Cloud"
  - Subtitle: "Facilitating continental-scale evaluation of historical and real-time hydrologic data at scale"
  - Images:
    - https://github.com/RTIInternational/teehr/blob/main/docs/images/teehr.png
    - https://github.com/RTIInternational/teehr/blob/main/docs/images/readme/CIROHLogo_200x200.png
  - Navbar: Include links to
    - Dashboard hub at `https://dashboards.teehr.rtiamanzi.org/hub`
    - TEEHR-Python repo: `https://github.com/RTIInternational/teehr`
    - TEEHR-Hub repo: `https://github.com/RTIInternational/teehr-hub`
    - TEEHR-Hub deployment: `https://hub.teehr.rtiamanzi.org/hub/spawn`
  - Action button: Sign up for the dashboards.
    - Should take you to the dashboard registration page (same as the sign up button on the dashboard hub page)
  - Action button: Request access
    - Should send an email to: ciroh.teehr@gmail.com
- **Main Content Area**:
  - Subsections
    - Includes background information and a summary of the TEEHR-Cloud framework
    - Nested subsection 1:
      - Can include information similar to this link: https://github.com/RTIInternational/teehr#the-teehr-cloud-framework
    - Nested subsection 2:
      - Data warehouse
    - Nested subsection 3:
      - Services (Evaluation Manager)

## 4. User Interactivity & Logic
- **TEEHR Icon Click**: Clicking the TEEHR icon image (https://github.com/RTIInternational/teehr/blob/main/docs/images/teehr.png) should always return you to the welcome page

## 5. Existing Code References for Inspiration
Copilot, mimic the code style found in:
- Styling pattern: `#file:frontend/src/components/common/Home.jsx`
- Style should be consistent with all dashboard pages
- Code and components should be reused wherever possible
