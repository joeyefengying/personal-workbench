import React from 'react';
import { render } from 'react-dom';
import { Provider } from 'react-redux';
import { BrowserRouter as Router } from 'react-router-dom';
import App from './App';
import LocaleProvider from './containers/LocaleProvider';
import store from './store/ConfigureStore';
import './styles/index.scss';

render(
  <Provider store={store as any}>
    <LocaleProvider>
      <Router>
        <App />
      </Router>
    </LocaleProvider>
  </Provider>,
  document.getElementById('root') as HTMLElement
);



// WEBPACK FOOTER //
// ./src/index.tsx