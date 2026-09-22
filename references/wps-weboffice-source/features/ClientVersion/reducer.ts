import { fromJS } from 'immutable';
import RequestState from '../../constants/RequestState';
import {
  FETCH_CLIENT_VERSION_FAIL,
  FETCH_CLIENT_VERSION_REQUEST,
  FETCH_CLIENT_VERSION_SUCCESS,
} from './constants';

const initState = fromJS({
  requestState: RequestState.SUCCESS,
  version: {},
  errorCode: '',
  errorLocaleKey: '',
});

function clientVersion(state: any = initState, action: any) {
  switch (action.type) {
    case FETCH_CLIENT_VERSION_REQUEST:
      return state.set('requestState', RequestState.PENDING);
    case FETCH_CLIENT_VERSION_FAIL:
      return state.merge(
        fromJS({
          ...action.payload,
          requestState: RequestState.FAILED,
        })
      );
    case FETCH_CLIENT_VERSION_SUCCESS:
      return state.merge(
        fromJS({
          requestState: RequestState.SUCCESS,
          version: action.payload,
        })
      );
    default:
      return state;
  }
}

export default clientVersion;



// WEBPACK FOOTER //
// ./src/features/ClientVersion/reducer.ts