"use client";

import { useEffect } from "react";

export function SaveApiKey({ apiKey }: { apiKey?: string }) {
  useEffect(() => {
    if (apiKey) {
      localStorage.setItem("marginalia_api_key", apiKey);
    }
  }, [apiKey]);

  return null;
}