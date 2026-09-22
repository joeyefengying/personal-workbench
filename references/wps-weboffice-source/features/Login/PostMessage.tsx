import React, { Component } from "react";
import { getQuery } from "../../utils/UrlUtil";
import "./index.scss";

export default class MiddleRedirect extends Component {
  constructor(props: any) {
    super(props);
  }
  public componentDidMount() {
    console.log('login-iframe');
    const url = getQuery('url');
    if(url) {
      window.parent.postMessage(`${url}`, window.location.href);
    } else {
      window.parent.postMessage(`${window.location.href}`, window.location.href);
    }
}
  public render() {
    return (
      <div className="login-redirect-page">
      </div>
    );
  }
}



// WEBPACK FOOTER //
// ./src/features/Login/PostMessage.tsx