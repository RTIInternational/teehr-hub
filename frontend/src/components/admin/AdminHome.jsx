import { Link } from 'react-router-dom';

const cards = [
  {
    title: 'API Keys',
    description: 'Create, review, and revoke API keys for administrative workflows.',
    to: '/admin/api-keys',
    buttonLabel: 'Manage API Keys',
  },
  {
    title: 'TEEHR Keycloak',
    description: 'Open Keycloak admin tools to manage users, groups, and clients.',
    to: '/admin/keycloak',
    buttonLabel: 'Open Keycloak Section',
  },
];

const AdminHome = () => {
  return (
    <div>
      <h4 className="mb-2">Admin Home</h4>
      <p className="text-muted mb-4">
        Use this workspace to manage platform administration tasks. Additional tools will be added over time.
      </p>

      <div className="row g-3">
        {cards.map((card) => (
          <div key={card.title} className="col-12 col-md-6">
            <div className="card h-100">
              <div className="card-body d-flex flex-column">
                <h5 className="card-title">{card.title}</h5>
                <p className="card-text text-muted">{card.description}</p>
                <div className="mt-auto">
                  <Link to={card.to} className="btn btn-outline-primary">
                    {card.buttonLabel}
                  </Link>
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
