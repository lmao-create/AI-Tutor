import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { ApiError } from "../api/types";

interface UseApiResult<T> {
  data: T | null;
  error: ApiError | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

/** Fetch a GET endpoint, with loading/error state and a manual refresh. */
export function useApi<T>(path: string | null): UseApiResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(Boolean(path));
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!path) {
      setData(null);
      setLoading(false);
      return;
    }
    let alive = true;
    setLoading(true);
    api
      .get<T>(path)
      .then((res) => {
        if (alive) {
          setData(res);
          setError(null);
        }
      })
      .catch((e: unknown) => {
        if (alive) {
          setError(
            e instanceof ApiError ? e : new ApiError(String(e), 0, "unknown"),
          );
        }
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [path, nonce]);

  const refresh = useCallback(async () => {
    setNonce((n) => n + 1);
  }, []);

  return { data, error, loading, refresh };
}

/** Run a POST on demand, exposing pending state and the error. */
export function useApiAction<P, R>(path: string) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<R | null>(null);

  const run = useCallback(
    async (body: P, customPath?: string): Promise<R | null> => {
      setPending(true);
      setError(null);
      try {
        const res = await api.post<R>(customPath ?? path, body);
        setResult(res);
        return res;
      } catch (e: unknown) {
        setError(
          e instanceof ApiError ? e : new ApiError(String(e), 0, "unknown"),
        );
        return null;
      } finally {
        setPending(false);
      }
    },
    [path],
  );

  return { run, pending, error, result };
}
