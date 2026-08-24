import { Link } from 'react-router-dom';

const KEYCLOAK_BASE_URL =
  import.meta.env.VITE_KEYCLOAK_URL || 'https://auth.teehr.local.app.garden';
const PREFECT_BASE_URL =
  import.meta.env.VITE_PREFECT_URL || 'https://prefect.teehr.local.app.garden';

const cards = [
  {
    title: 'API Keys',
    description: 'Create, review, and revoke API keys for administrative workflows.',
    to: '/admin/api-keys',
    buttonLabel: 'Manage API Keys',
  },
  {
    title: 'Keycloak',
    description: 'Manage users, groups, clients, and realm settings in the Keycloak admin console.',
    href: `${KEYCLOAK_BASE_URL}/admin/teehr/console/`,
    buttonLabel: 'Open Keycloak Admin',
    isExternal: true,
  },
  {
    title: 'Prefect',
    description: 'Access Prefect admin console to manage workflows and deployments.',
    href: PREFECT_BASE_URL,
    buttonLabel: 'Open Prefect',
    isExternal: true,
  },
];

const AdminHome = () => {
  return (
    <div className="p-3">
      <h4 className="mb-2">Admin Home</h4>
      <p className="text-muted mb-4">
        Use this workspace to manage platform administration tasks. Additional tools will be added over time.
      </p>

      <div className="row g-3">
        {cards.map((card) => (
          <div key={card.title} className="col-12 col-md-6 col-xl-4">
            <div className="card h-100">
              <div className="card-body d-flex flex-column">
                <h5 className="card-title">{card.title}</h5>
                <p className="card-text text-muted">{card.description}</p>
                <div className="mt-auto">
                  {card.isExternal ? (
                    <a href={card.href} target="_blank" rel="noopener noreferrer" className="btn btn-outline-primary">
                      {card.buttonLabel}
                    </a>
                  ) : (
                    <Link to={card.to} className="btn btn-outline-primary">
                      {card.buttonLabel}
                    </Link>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default AdminHome;
