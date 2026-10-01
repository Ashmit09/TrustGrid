import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import NavBar from "./components/NavBar";

// Pages
import Login    from "./pages/public/Login";
import Register from "./pages/public/Register";

// Buyer
import Products from "./pages/buyer/Products";
import Orders   from "./pages/buyer/Orders";
import TrustDashboard from "./pages/buyer/TrustDashboard";

// Seller
import AddProduct  from "./pages/seller/AddProduct";
import SellerOrders from "./pages/seller/SellerOrders";

// Admin
import AdminDashboard from "./pages/admin/AdminDashboard";

function ProtectedRoute({ children, roles }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/login" />;
  return children;
}

function AppRoutes() {
  const { user } = useAuth();
  return (
    <>
      {user && <NavBar />}
      <Routes>
        <Route path="/" element={<Navigate to="/login" />} />
        <Route path="/login"    element={<Login />} />
        <Route path="/register" element={<Register />} />

        {/* Buyer */}
        <Route path="/buyer/dashboard" element={<ProtectedRoute roles={["buyer"]}><Products /></ProtectedRoute>} />
        <Route path="/buyer/products"  element={<ProtectedRoute roles={["buyer"]}><Products /></ProtectedRoute>} />
        <Route path="/buyer/orders"    element={<ProtectedRoute roles={["buyer"]}><Orders /></ProtectedRoute>} />
        <Route path="/buyer/trust"     element={<ProtectedRoute roles={["buyer"]}><TrustDashboard /></ProtectedRoute>} />

        {/* Seller */}
        <Route path="/seller/dashboard"   element={<ProtectedRoute roles={["seller"]}><SellerOrders /></ProtectedRoute>} />
        <Route path="/seller/orders"      element={<ProtectedRoute roles={["seller"]}><SellerOrders /></ProtectedRoute>} />
        <Route path="/seller/add-product" element={<ProtectedRoute roles={["seller"]}><AddProduct /></ProtectedRoute>} />
        <Route path="/seller/trust"       element={<ProtectedRoute roles={["seller"]}><TrustDashboard /></ProtectedRoute>} />

        {/* Admin */}
        <Route path="/admin/dashboard" element={<ProtectedRoute roles={["admin"]}><AdminDashboard /></ProtectedRoute>} />

        <Route path="*" element={<Navigate to="/login" />} />
      </Routes>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
