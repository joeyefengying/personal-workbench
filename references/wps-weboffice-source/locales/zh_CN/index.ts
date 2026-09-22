import { flattenMessages } from '../flattenMessages';
import errorText from './errorText';
import uiText from './uiText';

export default {
  ...flattenMessages(uiText),
  ...flattenMessages(errorText),
};



// WEBPACK FOOTER //
// ./src/locales/zh_CN/index.ts