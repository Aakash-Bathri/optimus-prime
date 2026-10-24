import { useEffect, useState } from 'react';
import { get } from './lib/api';
import type { Page, Resource } from './lib/api';
import Execution from './Execution';

export default function App() {
  const [inventory, setInventory] = useState<Page<Resource> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setInventory(null);
    setError(null);
    Promise.all([
      get('/health', controller.signal),
      get<Page<Resource>>('/resources', controller.signal),
    ])
      .then(([, resources]) => setInventory(resources))
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(cause instanceof Error ? cause.message : 'Unable to connect');
        }
      });
    return () => controller.abort();
  }, [attempt]);

  return (
    <main>
      <header>
        <p className="eyebrow">DEVELOPMENT FOUNDATION</p>
        <h1>CloudPilot</h1>
        <p>The starting point for the team’s cloud optimization workspace.</p>
      </header>
      <section aria-labelledby="inventory-title">
        <div className="section-heading">
          <h2 id="inventory-title">Starter inventory</h2>
          <span>{error ? 'API unavailable' : inventory ? 'API connected' : 'Connecting to API'}</span>
        </div>
        {error ? (
          <div role="alert">
            <p>{error}. Check that the backend is running at the configured API address.</p>
            <button onClick={() => setAttempt(value => value + 1)}>Retry</button>
          </div>
        ) : !inventory ? (
          <p role="status">Loading resources…</p>
        ) : inventory.items.length === 0 ? (
          <p>No resources available.</p>
        ) : (
          <div className="table-scroll">
            <table>
              <thead><tr><th>Resource</th><th>Environment</th><th>Region</th><th>Source</th></tr></thead>
              <tbody>
                {inventory.items.map(resource => (
                  <tr key={resource.id}>
                    <td>{resource.name}</td><td>{resource.environment}</td>
                    <td>{resource.region}</td><td>{resource.provenance}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="note">One synthetic fixture with illustrative pricing. Analysis and recommendations are not implemented yet.</p>
      </section>
      <Execution />
    </main>
  );
}

