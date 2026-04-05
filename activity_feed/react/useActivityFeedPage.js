import { useEffect, useState } from "react";

function getLocalDateString(value) {
  if (typeof value === "string" && value.trim()) {
    return value.trim();
  }

  const resolvedDate = value instanceof Date ? value : new Date();
  const year = resolvedDate.getFullYear();
  const month = `${resolvedDate.getMonth() + 1}`.padStart(2, "0");
  const day = `${resolvedDate.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function buildActivityTimelineUrl({ baseUrl, instituteId, page = 1, date }) {
  const params = new URLSearchParams({
    institute: `${instituteId}`,
    page: `${page}`,
    date: getLocalDateString(date),
  });

  return `${baseUrl.replace(/\/$/, "")}/activity_feed/timeline/?${params.toString()}`;
}

function resolveErrorMessage(payload) {
  if (payload?.detail) {
    return payload.detail;
  }
  if (Array.isArray(payload?.date) && payload.date.length > 0) {
    return payload.date[0];
  }
  return "Unable to load activity feed.";
}

export async function fetchActivityFeedPage({
  baseUrl,
  instituteId,
  adminKey,
  page = 1,
  date,
  signal,
}) {
  const resolvedDate = getLocalDateString(date);
  const response = await fetch(
    buildActivityTimelineUrl({
      baseUrl,
      instituteId,
      page,
      date: resolvedDate,
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
    throw new Error(resolveErrorMessage(payload));
  }

  const institute = payload.results || {};

  return {
    institute,
    activities: institute.timeline || [],
    selectedDate: institute.date || resolvedDate,
    pagination: {
      count: payload.count || 0,
      page: payload.page || page,
      pageSize: payload.page_size || 20,
      totalPages: payload.total_pages || 0,
      next: payload.next,
      previous: payload.previous,
    },
    raw: payload,
  };
}

export function useActivityFeedPage(options) {
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

    fetchActivityFeedPage({
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
    options.date,
    options.instituteId,
    options.page,
  ]);

  return state;
}
