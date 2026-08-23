import { useEffect, useMemo, useRef, useState } from 'react';
import { runFailureSimulation, DEFAULT_MAX_HOURS } from '../api/turbineSimulationApi';

const PAGE_SIZE = 10;

const initialForm = {
  rpm: 3000,
  stress_mpa: 300,
};

/**
 * Encapsulates everything the dashboard needs to run a simulation and
 * page through its results. Import this hook anywhere you want the same
 * simulate → paginate behavior without re-wiring API calls or state.
 */
export function useTurbineSimulation() {
  const [form, setForm] = useState(initialForm);
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);

  const abortRef = useRef(null);

  // Cancel any in-flight request if the component using this hook unmounts.
  useEffect(() => () => abortRef.current?.abort(), []);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const runSimulation = async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setError('');
    setPage(1);

    try {
      const data = await runFailureSimulation({
        rpm: form.rpm,
        stressMpa: form.stress_mpa,
        signal: controller.signal,
      });
      setResult(data);
    } catch (apiError) {
      if (apiError.name !== 'AbortError') {
        setError(apiError.message || 'Unable to reach the simulation API.');
        setResult(null);
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Prefer values the backend actually simulated with over raw form inputs —
  // the API response is the source of truth once a run completes.
  const rows = result?.degradation_curve ?? [];
  const displayedRpm = result?.rpm ?? Number(form.rpm);
  const displayedStress = result?.stress_mpa ?? Number(form.stress_mpa);
  const displayedMaxHours = result?.max_hours ?? DEFAULT_MAX_HOURS;
  const estimatedLifeHours = Number(result?.estimated_operating_life_hours ?? 0);

  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const pagedRows = useMemo(
    () => rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [rows, page]
  );

  const goToPage = (next) => setPage(Math.min(Math.max(1, next), totalPages));

  return {
    form,
    handleChange,
    runSimulation,
    isLoading,
    error,
    result,
    rows,
    pagedRows,
    page,
    totalPages,
    goToPage,
    displayedRpm,
    displayedStress,
    displayedMaxHours,
    estimatedLifeHours,
    pageSize: PAGE_SIZE,
  };
}
