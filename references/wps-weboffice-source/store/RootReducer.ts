import { combineReducers } from 'redux';
import clientVersion from '../features/ClientVersion/reducer';
import language from '../features/Language/reducer';

const appReducer = combineReducers({
  clientVersion,
  language,
});

const rootReducer = (state: any, action: any) => {
  return appReducer(state, action);
};

export default rootReducer;



// WEBPACK FOOTER //
// ./src/store/RootReducer.ts