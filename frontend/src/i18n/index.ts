import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import ptBRCommon from './locales/pt-BR/common.json';
import ptBRDashboard from './locales/pt-BR/dashboard.json';
import ptBRTournaments from './locales/pt-BR/tournaments.json';
import ptBRStudy from './locales/pt-BR/study.json';
import ptBRAuth from './locales/pt-BR/auth.json';
import ptBRAicoach from './locales/pt-BR/aicoach.json';
import ptBRCoaches from './locales/pt-BR/coaches.json';
import ptBRProfile from './locales/pt-BR/profile.json';
import ptBRReplayer from './locales/pt-BR/replayer.json';
import ptBRLanding from './locales/pt-BR/landing.json';
import ptBRGhost from './locales/pt-BR/ghost.json';
import ptBRDocs from './locales/pt-BR/docs.json';
import ptBRSparring from './locales/pt-BR/sparring.json';
import ptBRTraining from './locales/pt-BR/training.json';

import enCommon from './locales/en/common.json';
import enDashboard from './locales/en/dashboard.json';
import enTournaments from './locales/en/tournaments.json';
import enStudy from './locales/en/study.json';
import enAuth from './locales/en/auth.json';
import enAicoach from './locales/en/aicoach.json';
import enCoaches from './locales/en/coaches.json';
import enProfile from './locales/en/profile.json';
import enReplayer from './locales/en/replayer.json';
import enLanding from './locales/en/landing.json';
import enGhost from './locales/en/ghost.json';
import enDocs from './locales/en/docs.json';
import enSparring from './locales/en/sparring.json';
import enTraining from './locales/en/training.json';

import esCommon from './locales/es/common.json';
import esDashboard from './locales/es/dashboard.json';
import esTournaments from './locales/es/tournaments.json';
import esStudy from './locales/es/study.json';
import esAuth from './locales/es/auth.json';
import esAicoach from './locales/es/aicoach.json';
import esCoaches from './locales/es/coaches.json';
import esProfile from './locales/es/profile.json';
import esReplayer from './locales/es/replayer.json';
import esLanding from './locales/es/landing.json';
import esGhost from './locales/es/ghost.json';
import esDocs from './locales/es/docs.json';
import esSparring from './locales/es/sparring.json';
import esTraining from './locales/es/training.json';

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
        aicoach: ptBRAicoach,
        coaches: ptBRCoaches,
        profile: ptBRProfile,
        replayer: ptBRReplayer,
        landing: ptBRLanding,
        ghost: ptBRGhost,
        docs: ptBRDocs,
        sparring: ptBRSparring,
        training: ptBRTraining,
      },
      en: {
        common: enCommon,
        dashboard: enDashboard,
        tournaments: enTournaments,
        study: enStudy,
        auth: enAuth,
        aicoach: enAicoach,
        coaches: enCoaches,
        profile: enProfile,
        replayer: enReplayer,
        landing: enLanding,
        ghost: enGhost,
        docs: enDocs,
        sparring: enSparring,
        training: enTraining,
      },
      es: {
        common: esCommon,
        dashboard: esDashboard,
        tournaments: esTournaments,
        study: esStudy,
        auth: esAuth,
        aicoach: esAicoach,
        coaches: esCoaches,
        profile: esProfile,
        replayer: esReplayer,
        landing: esLanding,
        ghost: esGhost,
        docs: esDocs,
        sparring: esSparring,
        training: esTraining,
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
