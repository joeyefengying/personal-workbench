import React, { Component } from "react";
import { HashRouter, Route } from "react-router-dom";
import ClientVersion from "./features/ClientVersion";
import Home from "./features/Home";
import Language from "./features/Language";
import Login from "./features/Login";
import NoAuthPage from "./features/Login/NoAuth";
import MiddleRedirect from "./features/Login/PostMessage";

class App extends Component {
  public render() {
    return (
      <HashRouter>
        <div className="route-app">
          <Route exact path="/" component={Home} />
          <Route path="/client-version" component={ClientVersion} />
          <Route path="/language" component={Language} />
          <Route path="/qrcode-login" component={Login} />
          <Route path="/middle-redirect" component={MiddleRedirect} />
          <Route path="/no-auth" component={NoAuthPage} />

        </div>
      </HashRouter>
    );
  }
}

export default App;



// WEBPACK FOOTER //
// ./src/App.tsx