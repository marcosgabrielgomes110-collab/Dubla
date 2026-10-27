import { Route, Routes } from "react-router-dom";

import { Layout } from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import Models from "@/pages/Models";
import Movies from "@/pages/Movies";
import Pipeline from "@/pages/Pipeline";
import Secrets from "@/pages/Secrets";
import SettingsPage from "@/pages/Settings";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="pipeline" element={<Pipeline />} />
        <Route path="movies" element={<Movies />} />
        <Route path="models" element={<Models />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="secrets" element={<Secrets />} />
      </Route>
    </Routes>
  );
}
