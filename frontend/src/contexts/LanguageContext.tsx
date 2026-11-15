import * as React from "react";
import i18n from "../i18n";

export type AppLanguage = "pt" | "en";

const STORAGE_KEY = "kultiva:language";

interface LanguageContextValue {
  language: AppLanguage;
  setLanguage: (lang: AppLanguage) => void;
}

const LanguageContext = React.createContext<LanguageContextValue>({
  language: "pt",
  setLanguage: () => {},
});

function readStoredLanguage(): AppLanguage {
  if (typeof window === "undefined") return "pt";
  const raw = window.localStorage.getItem(STORAGE_KEY);
  return raw === "en" ? "en" : "pt";
}

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = React.useState<AppLanguage>(readStoredLanguage);

  const setLanguage = React.useCallback((lang: AppLanguage) => {
    setLanguageState(lang);
    void i18n.changeLanguage(lang);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, lang);
    }
  }, []);

  const value = React.useMemo(
    () => ({ language, setLanguage }),
    [language, setLanguage]
  );

  return (
    <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextValue {
  return React.useContext(LanguageContext);
}

