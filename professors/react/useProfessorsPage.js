import { useEffect, useState } from "react";

function appendIfPresent(params, key, value) {
  const normalizedValue = `${value ?? ""}`.trim();
  if (normalizedValue) {
    params.set(key, normalizedValue);
  }
}

function buildProfessorListUrl({
  baseUrl,
  instituteId,
  page = 1,
  search = "",
  name = "",
  employeeId = "",
  department = "",
}) {
  const params = new URLSearchParams({
    institute: `${instituteId}`,
    page: `${page}`,
  });

  appendIfPresent(params, "search", search);
  appendIfPresent(params, "name", name);
  appendIfPresent(params, "employee_id", employeeId);
  appendIfPresent(params, "department", department);

  return `${baseUrl.replace(/\/$/, "")}/professors/professors/?${params.toString()}`;
}

export async function fetchProfessorsPage({
  baseUrl,
  instituteId,
  adminKey,
  page = 1,
  search = "",
  name = "",
  employeeId = "",
  department = "",
  signal,
}) {
  const response = await fetch(
    buildProfessorListUrl({
      baseUrl,
      instituteId,
      page,
      search,
      name,
      employeeId,
      department,
    }),
    {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        "X-Admin-Key": adminKey,
      },
      signal,
    },
  );

  const payload = await response.json();

  if (!response.ok) {
    throw new Error(payload.detail || "Unable to load professors.");
  }

  const institute = payload.results || {};

  return {
    institute,
    professors: institute.professors || [],
    pagination: {
      count: payload.count || 0,
      page: payload.page || page,
      pageSize: payload.page_size || 10,
      totalPages: payload.total_pages || 0,
      next: payload.next,
      previous: payload.previous,
    },
    raw: payload,
  };
}

export function useProfessorsPage(options) {
  const [state, setState] = useState({
    data: null,
    loading: true,
    error: null,
  });

  useEffect(() => {
    const controller = new AbortController();

    setState((currentState) => ({
      ...currentState,
      loading: true,
      error: null,
    }));

    fetchProfessorsPage({
      ...options,
      signal: controller.signal,
    })
      .then((data) => {
        setState({
          data,
          loading: false,
          error: null,
        });
      })
      .catch((error) => {
        if (error.name === "AbortError") {
          return;
        }

        setState({
          data: null,
          loading: false,
          error,
        });
      });

    return () => {
      controller.abort();
    };
  }, [
    options.adminKey,
    options.baseUrl,
    options.department,
    options.employeeId,
    options.instituteId,
    options.name,
    options.page,
    options.search,
  ]);

  return state;
}
