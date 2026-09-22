import { all, call, fork, put, take } from 'redux-saga/effects';
import transformError2ExceptionInfo from '../../exceptions/ExceptionTransformer';
import ClientVersionBO from '../../models/bo/ClientVersionBO';
import { fetchClientVersion } from '../../services/ClientVersionService';
import {
  fetchClientVersionFail,
  FetchClientVersionRequest,
  fetchClientVersionSuccess,
} from './action';
import { FETCH_CLIENT_VERSION_REQUEST } from './constants';

function* watchFetchClientVersion() {
  while (true) {
    try {
      const action: FetchClientVersionRequest = yield take(FETCH_CLIENT_VERSION_REQUEST);
      const version: ClientVersionBO = yield call(fetchClientVersion, action.payload);
      yield put(fetchClientVersionSuccess(version));
    } catch (error) {
      yield put(fetchClientVersionFail(transformError2ExceptionInfo(error)));
    }
  }
}

export default function* clientVersionSaga() {
  yield all([fork(watchFetchClientVersion)]);
}



// WEBPACK FOOTER //
// ./src/features/ClientVersion/saga.ts