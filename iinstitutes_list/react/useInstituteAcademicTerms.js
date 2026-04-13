import { useEffect, useState } from "react";

const TERM_CACHE_PREFIX = "institute-academic-terms";
const DEFAULT_TERM_CACHE_SECRET = "institute-academic-terms-v1";

function normalizeText(value) {
  return `${value ?? ""}`.trim().toLowerCase();
}

function toBaseUrl(value) {
  return `${value ?? ""}`.replace(/\/$/, "");
}

function appendIfPresent(params, key, value) {
  const normalizedValue = `${value ?? ""}`.trim();
  if (normalizedValue) {
    params.set(key, normalizedValue);
  }
}

function toUint8Array(value) {
  return new TextEncoder().encode(value);
}

function getStorageKey(instituteId) {
  return `${TERM_CACHE_PREFIX}:${instituteId}`;
}

function getBrowserCrypto() {
  if (typeof window === "undefined") {
    return null;
  }

  return window.crypto?.subtle ? window.crypto : null;
}

function bytesToBase64(bytes) {
  let binary = "";
  bytes.forEach((value) => {
    binary += String.fromCharCode(value);
  });
  return btoa(binary);
}

function base64ToBytes(value) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);

  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }

  return bytes;
}

async function deriveEncryptionKey({ instituteId, encryptionSecret }) {
  const browserCrypto = getBrowserCrypto();
  if (!browserCrypto) {
    return null;
  }

  const keyMaterial = await browserCrypto.subtle.importKey(
    "raw",
    toUint8Array(encryptionSecret),
    "PBKDF2",
    false,
    ["deriveKey"],
  );

  return browserCrypto.subtle.deriveKey(
    {
      name: "PBKDF2",
      salt: toUint8Array(`institute:${instituteId}`),
      iterations: 100000,
      hash: "SHA-256",
    },
    keyMaterial,
    {
      name: "AES-GCM",
      length: 256,
    },
    false,
    ["encrypt", "decrypt"],
  );
}

async function encryptCacheValue({ instituteId, value, encryptionSecret }) {
  const browserCrypto = getBrowserCrypto();
  if (!browserCrypto) {
    return null;
  }

  const key = await deriveEncryptionKey({ instituteId, encryptionSecret });
  if (!key) {
    return null;
  }

  const iv = browserCrypto.getRandomValues(new Uint8Array(12));
  const encodedValue = toUint8Array(JSON.stringify(value));
  const encryptedValue = await browserCrypto.subtle.encrypt(
    { name: "AES-GCM", iv },
    key,
    encodedValue,
  );

  return JSON.stringify({
    iv: bytesToBase64(iv),
    value: bytesToBase64(new Uint8Array(encryptedValue)),
  });
}

async function decryptCacheValue({ instituteId, encryptedValue, encryptionSecret }) {
  const browserCrypto = getBrowserCrypto();
  if (!browserCrypto || !encryptedValue) {
    return null;
  }

  try {
    const parsedValue = JSON.parse(encryptedValue);
    const key = await deriveEncryptionKey({ instituteId, encryptionSecret });
    if (!key) {
      return null;
    }

    const decryptedValue = await browserCrypto.subtle.decrypt(
      {
        name: "AES-GCM",
        iv: base64ToBytes(parsedValue.iv),
      },
      key,
      base64ToBytes(parsedValue.value),
    );

    return JSON.parse(new TextDecoder().decode(decryptedValue));
  } catch (error) {
    return null;
  }
}

function normalizeInstituteAcademicTermsPayload(payload, instituteId) {
  if (!payload) {
    return {
      id: instituteId ?? null,
      instituteName: "",
      academicTermsType: null,
      academicTerms: [],
    };
  }

  if (!Array.isArray(payload) && Array.isArray(payload.academic_terms)) {
    const sourcePayload = payload || {};
    return {
      id: sourcePayload.id ?? instituteId ?? null,
      instituteName: sourcePayload.institute_name || sourcePayload.name || "",
      academicTermsType: sourcePayload.academic_terms_type || null,
      academicTerms: sourcePayload.academic_terms.filter((item) => normalizeText(item)),
    };
  }

  const sourceItems = Array.isArray(payload) ? payload : [];
  const firstItem = sourceItems[0] || {};
  const sourcePayload = Array.isArray(payload) ? payload[0] || {} : payload || {};
  return {
    id: firstItem.institute ?? instituteId ?? sourcePayload.id ?? null,
    instituteName: firstItem.institute_name || sourcePayload.institute_name || sourcePayload.name || "",
    academicTermsType: null,
    academicTerms: sourceItems
      .map((item) => item?.name)
      .filter((item) => normalizeText(item)),
  };
}

export async function readCachedInstituteAcademicTerms({
  instituteId,
  encryptionSecret = DEFAULT_TERM_CACHE_SECRET,
}) {
  if (typeof window === "undefined" || !instituteId) {
    return null;
  }

  const rawValue = window.localStorage.getItem(getStorageKey(instituteId));
  if (!rawValue) {
    return null;
  }

  const parsedValue = await decryptCacheValue({
    instituteId,
    encryptedValue: rawValue,
    encryptionSecret,
  });

  return parsedValue || null;
}

export async function writeCachedInstituteAcademicTerms({
  instituteId,
  payload,
  encryptionSecret = DEFAULT_TERM_CACHE_SECRET,
}) {
  if (typeof window === "undefined" || !instituteId) {
    return;
  }

  const encryptedValue = await encryptCacheValue({
    instituteId,
    value: payload,
    encryptionSecret,
  });

  if (!encryptedValue) {
    return;
  }

  window.localStorage.setItem(getStorageKey(instituteId), encryptedValue);
}

export function clearCachedInstituteAcademicTerms(instituteId) {
  if (typeof window === "undefined" || !instituteId) {
    return;
  }

  window.localStorage.removeItem(getStorageKey(instituteId));
}

export function buildInstituteAcademicTermsUrl({ baseUrl, instituteId }) {
  const params = new URLSearchParams({
    institute: `${instituteId}`,
  });

  return `${toBaseUrl(baseUrl)}/default_activities/academic-terms/?${params.toString()}`;
}

export async function fetchInstituteAcademicTerms({
  baseUrl,
  instituteId,
  adminKey,
  signal,
  preferCache = true,
  encryptionSecret = DEFAULT_TERM_CACHE_SECRET,
}) {
  if (!instituteId) {
    throw new Error("Institute id is required.");
  }

  if (preferCache) {
    const cachedValue = await readCachedInstituteAcademicTerms({
      instituteId,
      encryptionSecret,
    });
    if (cachedValue) {
      return {
        ...cachedValue,
        source: "localstorage",
      };
    }
  }

  const response = await fetch(
    buildInstituteAcademicTermsUrl({ baseUrl, instituteId }),
    {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        ...(adminKey ? { "X-Admin-Key": adminKey } : {}),
      },
      signal,
    },
  );

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Unable to load institute academic terms.");
  }

  const normalizedPayload = normalizeInstituteAcademicTermsPayload(payload, instituteId);
  const cachePayload = {
    ...normalizedPayload,
    cachedAt: new Date().toISOString(),
  };

  await writeCachedInstituteAcademicTerms({
    instituteId,
    payload: cachePayload,
    encryptionSecret,
  });

  return {
    ...cachePayload,
    source: "api",
  };
}

export function resolveAcademicTermsOptions({
  termsConfig,
  syllabusCourses = [],
  className = "",
  branch = "",
}) {
  if (!termsConfig) {
    return [];
  }

  const normalizedClassName = normalizeText(className);
  const normalizedBranch = normalizeText(branch);

  if (normalizedClassName && normalizedBranch && Array.isArray(syllabusCourses)) {
    const course = syllabusCourses.find(
      (item) => normalizeText(item?.name) === normalizedClassName,
    );
    const branchData = course?.branches?.find(
      (item) => normalizeText(item?.name) === normalizedBranch,
    );
    const branchTerms = (branchData?.academic_terms || [])
      .map((item) => item?.name)
      .filter((item) => normalizeText(item));

    if (branchTerms.length > 0) {
      return branchTerms;
    }
  }

  return termsConfig.academicTerms || [];
}

export function buildInstituteHierarchyUrl({
  baseUrl,
  path,
  instituteId,
  className,
  branch,
  academicTerm,
  extraParams = {},
}) {
  const params = new URLSearchParams({
    institute: `${instituteId}`,
  });

  appendIfPresent(params, "class_name", className);
  appendIfPresent(params, "branch", branch);
  appendIfPresent(params, "academic_term", academicTerm);

  Object.entries(extraParams).forEach(([key, value]) => {
    appendIfPresent(params, key, value);
  });

  return `${toBaseUrl(baseUrl)}${path}?${params.toString()}`;
}

export async function fetchInstituteHierarchyData({
  baseUrl,
  path,
  instituteId,
  adminKey,
  className,
  branch,
  academicTerm,
  extraParams = {},
  signal,
}) {
  const response = await fetch(
    buildInstituteHierarchyUrl({
      baseUrl,
      path,
      instituteId,
      className,
      branch,
      academicTerm,
      extraParams,
    }),
    {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
        ...(adminKey ? { "X-Admin-Key": adminKey } : {}),
      },
      signal,
    },
  );

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Unable to load institute data.");
  }

  return payload;
}

export function useInstituteAcademicTerms(options) {
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

    fetchInstituteAcademicTerms({
      ...options,
      signal: controller.signal,
    })
      .then((termsConfig) => {
        setState({
          data: {
            ...termsConfig,
            dropdownOptions: resolveAcademicTermsOptions({
              termsConfig,
              syllabusCourses: options.syllabusCourses,
              className: options.className,
              branch: options.branch,
            }),
          },
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
    options.branch,
    options.className,
    options.encryptionSecret,
    options.instituteId,
    options.preferCache,
    options.syllabusCourses,
  ]);

  return state;
}
