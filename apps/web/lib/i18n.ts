"use client";

import { messages } from "@novaion/shared/i18n/messages";
import type { Language } from "@novaion/shared/types";
import type { ReactNode } from "react";
import { createContext, useContext, useEffect, useMemo, useState } from "react";

type I18nContextValue = {
  language: Language;
  setLanguage: (language: Language) => void;
  t: (key: string) => string;
};

const I18nContext = createContext<I18nContextValue | null>(null);

const supported: Language[] = ["en", "zh", "es"];

function browserLanguage(): Language {
  if (typeof navigator === "undefined") return "en";
  const lang = navigator.language.toLowerCase();
  if (lang.startsWith("zh")) return "zh";
  if (lang.startsWith("es")) return "es";
  return "en";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>("en");

  useEffect(() => {
    const saved = window.localStorage.getItem("novaion-language") as Language | null;
    setLanguageState(saved && supported.includes(saved) ? saved : browserLanguage());
  }, []);

  const setLanguage = (next: Language) => {
    const normalized = next === "es" ? "en" : next;
    setLanguageState(normalized);
    window.localStorage.setItem("novaion-language", normalized);
    fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/users/preferences`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: process.env.NEXT_PUBLIC_DEFAULT_USER_EMAIL,
        language: normalized,
      }),
    }).catch(() => undefined);
  };

  const value = useMemo<I18nContextValue>(
    () => ({
      language,
      setLanguage,
      t: (key: string) => messages[language]?.[key] ?? messages.en[key] ?? key,
    }),
    [language],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const value = useContext(I18nContext);
  if (!value) {
    throw new Error("useI18n must be used within I18nProvider");
  }
  return value;
}
