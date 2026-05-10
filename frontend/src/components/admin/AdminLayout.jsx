import { NavLink, Outlet } from 'react-router-dom';

const navItems = [
  {
    key: 'admin-home',
    label: 'Admin Home',
    path: '/admin',
  },
  {
    key: 'api-keys',
    label: 'API Keys',
    path: '/admin/api-keys',
  },
  {
    key: 'teehr-keycloak',
    label: 'TEEHR Keycloak',
    path: '/admin/keycloak',
  },
];

const AdminLayout = () => {
  return (
    <div className="container-fluid py-4">
      <div className="row g-4">
        <aside className="col-12 col-lg-3 col-xl-2">
          <div className="card h-100">
            <div className="card-body">
              <h5 className="card-title mb-3">Admin</h5>
              <div className="nav nav-pills flex-column gap-2">
                {navItems.map((item) => (
                  <NavLink
                    key={item.key}
                    to={item.path}
                    className={({ isActive }) =>
                      `btn text-start ${isActive ? 'btn-primary' : 'btn-outline-secondary'}`
                    }
                  >
                    {item.label}
                  </NavLink>
                ))}
              </div>
            </div>
          </div>
        </aside>

        <section className="col-12 col-lg-9 col-xl-10">
          <Outlet />
        </section>
      </div>
    </div>
  );
};

export default AdminLayout;
