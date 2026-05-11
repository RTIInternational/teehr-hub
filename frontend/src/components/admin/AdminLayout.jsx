import { Outlet } from 'react-router-dom';

const AdminLayout = () => {
  return (
    <div className="container-fluid py-4">
      <Outlet />
    </div>
  );
};

export default AdminLayout;
