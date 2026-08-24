const KEYCLOAK_BASE_URL =
  import.meta.env.VITE_KEYCLOAK_URL || 'https://auth.teehr.local.app.garden';

const KeycloakAdmin = () => {
  const keycloakAdminUrl = `${KEYCLOAK_BASE_URL}/admin/teehr/console/`;

  return (
    <div className="card">
      <div className="card-body">
        <h4 className="card-title mb-3">TEEHR Keycloak</h4>
        <p className="text-muted mb-3">
          Manage users, groups, clients, and realm settings in the Keycloak admin console.
        </p>

        <a
          href={keycloakAdminUrl}
          target="_blank"
          rel="noreferrer"
          className="btn btn-primary"
        >
          Open Keycloak Admin Console
        </a>
      </div>
    </div>
  );
};

export default KeycloakAdmin;
