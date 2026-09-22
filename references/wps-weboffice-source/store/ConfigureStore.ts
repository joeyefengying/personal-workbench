/**
 * 创建Store
 */
import { applyMiddleware, compose, createStore, Middleware } from 'redux';
import createSagaMiddleware from 'redux-saga';
import rootReducer from './RootReducer';
import rootSaga from './RootSaga';

function configureStore(initialState?: any) {
  const sagaMiddleware = createSagaMiddleware();
  const middleware: Middleware[] = [sagaMiddleware];

  const composeEnhancers =
    (window && (window as any).__REDUX_DEVTOOLS_EXTENSION_COMPOSE__) || compose;

  const enhancers =
    process.env.NODE_ENV === 'production'
      ? applyMiddleware(...middleware)
      : composeEnhancers(applyMiddleware(...middleware));

  return {
    ...createStore(rootReducer, initialState, enhancers),
    runSaga: sagaMiddleware.run,
  };
}

const store = configureStore();
store.runSaga(rootSaga);

export default store;



// WEBPACK FOOTER //
// ./src/store/ConfigureStore.ts