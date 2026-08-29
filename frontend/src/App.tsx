import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Analytics } from "@vercel/analytics/react";
import { AppShell } from "./components/layout/AppShell";
import { Dashboard } from "./pages/Dashboard";
import { NewJob } from "./pages/NewJob";
import { JobsPage } from "./pages/Jobs";
import { JobDetails } from "./pages/JobDetails";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<Dashboard />} />
          <Route path="new" element={<NewJob />} />
          <Route path="jobs" element={<JobsPage />} />
          <Route path="jobs/:jobId" element={<JobDetails />} />

        </Route>
      </Routes>
      <Analytics />
    </BrowserRouter>
  );
}
