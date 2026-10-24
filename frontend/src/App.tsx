import { NavLink, Route, Routes } from "react-router";
import { useProposedCount } from "./api/hooks";
import { Overview } from "./screens/Overview";
import { Library } from "./screens/Library";
import { ActivityScreen, RideScreen } from "./screens/Activity";
import { Science } from "./screens/Science";
import { SettingsScreen } from "./screens/Settings";

export function App() {
  const { data: proposed } = useProposedCount();
  return (
    <>
      <header className="topbar">
        <span className="brand">Open Cycling Science</span>
        <nav aria-label="Main">
          <NavLink to="/" end>Overview</NavLink>
          <NavLink to="/library">Library{proposed ? <span className="badge" title="Possible duplicate rides to review">{proposed}</span> : null}</NavLink>
          <NavLink to="/science">Science</NavLink>
          <NavLink to="/settings">Settings</NavLink>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/library/*" element={<Library />} />
          <Route path="/activities/:id" element={<ActivityScreen />} />
          <Route path="/rides/:id" element={<RideScreen />} />
          <Route path="/science" element={<Science />} />
          <Route path="/science/:metricId" element={<Science />} />
          <Route path="/settings" element={<SettingsScreen />} />
          <Route path="*" element={<p>Page not found.</p>} />
        </Routes>
      </main>
    </>
  );
}
