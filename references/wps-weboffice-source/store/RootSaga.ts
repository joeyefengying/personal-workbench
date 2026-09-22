import { call, spawn } from 'redux-saga/effects';
import clientVersionSaga from '../features/ClientVersion/saga';

export default function* rootSaga() {
  const sagas = [clientVersionSaga];
  yield sagas.map(saga =>
    spawn(function*() {
      while (true) {
        try {
          yield call(saga);
        } catch (error) {
          // 处理异常
        }
      }
    })
  );
}



// WEBPACK FOOTER //
// ./src/store/RootSaga.ts