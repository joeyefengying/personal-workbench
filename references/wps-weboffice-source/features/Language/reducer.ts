import LanguageType from '../../constants/LanguageType';
import { CHANGE_LANGUAGE } from './constants';

function language(state: any = LanguageType.EN, action: any) {
  return action.type === CHANGE_LANGUAGE ? action.payload : state;
}

export default language;



// WEBPACK FOOTER //
// ./src/features/Language/reducer.ts