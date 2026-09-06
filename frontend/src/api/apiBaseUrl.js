const LOCAL_API_URL = 'http://localhost:8000';
const PRODUCTION_API_URL = '/api';

export const API_BASE_URL =
  import.meta.env.DEV
    ? import.meta.env.VITE_API_BASE_URL || LOCAL_API_URL
    : PRODUCTION_API_URL;