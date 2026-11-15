import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import enUS from "./locales/en-US.json";
import ptBR from "./locales/pt-BR.json";

const STORAGE_KEY = "kultiva:language";

function getInitialLanguage(): "pt" | "en" {
  if (typeof window === "undefined") return "en";
  return window.localStorage.getItem(STORAGE_KEY) === "pt" ? "pt" : "en";
}

void i18n.use(initReactI18next).init({
  resources: {
    pt: { translation: ptBR },
    "pt-BR": { translation: ptBR },
    en: { translation: enUS },
    "en-US": { translation: enUS },
  },
  lng: getInitialLanguage(),
  fallbackLng: "en",
  interpolation: {
    escapeValue: false,
  },
});

export default i18n;

