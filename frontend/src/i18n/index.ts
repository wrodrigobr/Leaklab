import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import ptBRCommon from './locales/pt-BR/common.json';
import ptBRDashboard from './locales/pt-BR/dashboard.json';
import ptBRTournaments from './locales/pt-BR/tournaments.json';
import ptBRStudy from './locales/pt-BR/study.json';
import ptBRAuth from './locales/pt-BR/auth.json';

import enCommon from './locales/en/common.json';
import enDashboard from './locales/en/dashboard.json';
import enTournaments from './locales/en/tournaments.json';
import enStudy from './locales/en/study.json';
import enAuth from './locales/en/auth.json';

import esCommon from './locales/es/common.json';
import esDashboard from './locales/es/dashboard.json';
import esTournaments from './locales/es/tournaments.json';
import esStudy from './locales/es/study.json';
import esAuth from './locales/es/auth.json';

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      'pt-BR': {
        common: ptBRCommon,
        dashboard: ptBRDashboard,
        tournaments: ptBRTournaments,
        study: ptBRStudy,
        auth: ptBRAuth,
      },
      en: {
        common: enCommon,
        dashboard: enDashboard,
        tournaments: enTournaments,
        study: enStudy,
        auth: enAuth,
      },
      es: {
        common: esCommon,
        dashboard: esDashboard,
        tournaments: esTournaments,
        study: esStudy,
        auth: esAuth,
      },
    },
    fallbackLng: 'pt-BR',
    defaultNS: 'common',
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: 'leaklab_lang',
    },
    interpolation: {
      escapeValue: false,
    },
  });

export default i18n;
