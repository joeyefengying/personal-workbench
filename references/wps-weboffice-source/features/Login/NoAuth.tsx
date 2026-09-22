import React, { Component } from "react";
import { isMobileClient } from "../../utils/CommonUtil";
import "./index.scss";

export default class NoAuthPage extends Component {
  constructor(props: any) {
    super(props);
  }
  public componentDidMount() {
    console.log('no-auth-login-iframe');
    const isMobile = isMobileClient();
    if(!isMobile) {
      window.parent.postMessage(`${window.location.href}`, window.location.href);
      if(window.parent === window) {
        // 短信登录
        window.location.href = window.location.origin.replace('wps', 'web') + `/drive/preview/no-auth`;
      }
    } else {
      // tslint:disable-next-line:no-commented-code
      // 手机端直接跳转没权限页面
      // const fileId = window.location.href.split('fileId=')[1].replace('&redirect=yes', '');
      window.location.href = window.location.origin.replace('wps', 'web') + `/drive/preview/no-auth`;
    }
}
  public render() {
    return (
      <div className="no-auth-redirect-page">
      </div>
    );
  }
}



// WEBPACK FOOTER //
// ./src/features/Login/NoAuth.tsx