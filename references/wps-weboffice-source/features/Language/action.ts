import LanguageType from '../../constants/LanguageType';
import { CHANGE_LANGUAGE } from './constants';

export interface ChangeLanguage {
  type: CHANGE_LANGUAGE;
  payload: LanguageType;
}

export function changeLanguage(lang: LanguageType): ChangeLanguage {
  return {
    type: CHANGE_LANGUAGE,
    payload: lang,
  };
}



// WEBPACK FOOTER //
// ./src/features/Language/action.ts