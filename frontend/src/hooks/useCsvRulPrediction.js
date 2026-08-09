import { useMemo, useRef, useState } from 'react';
import { uploadCsvForPrediction } from '../api/turbineUploadApi';

const PAGE_SIZE = 8;

/**
 * Encapsulates CSV selection, upload, and paginated results — mirrors
 * useTurbineSimulation's simulate → paginate shape.
 */
export function useCsvRulPrediction() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [result, setResult] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);

  const abortRef = useRef(null);

  const handleFileSelect = (event) => {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
    setError('');
  };

  const runPrediction = async () => {
    if (!selectedFile) {
      setError('Choose a CSV file first.');
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setIsLoading(true);
    setError('');
    setPage(1);

    try {
      const data = await uploadCsvForPrediction({ file: selectedFile, signal: controller.signal });
      setResult(data);
    } catch (apiError) {
      if (apiError.name !== 'AbortError') {
        setError(apiError.message || 'Unable to reach the prediction API.');
        setResult(null);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const reset = () => {
    setSelectedFile(null);
    setResult(null);
    setError('');
    setPage(1);
  };

  const rows = result?.predictions ?? [];
  const totalPages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const pagedRows = useMemo(
    () => rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [rows, page]
  );

  const goToPage = (next) => setPage(Math.min(Math.max(1, next), totalPages));

  return {
    selectedFile,
    handleFileSelect,
    runPrediction,
    reset,
    isLoading,
    error,
    result,
    rows,
    pagedRows,
    page,
    totalPages,
    goToPage,
    pageSize: PAGE_SIZE,
  };
}