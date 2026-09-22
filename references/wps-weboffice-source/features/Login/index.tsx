import { Button, Input, message, Select, Tooltip } from "antd";
import React, { Component } from "react";
import { fetchQrcodeUrl, SMSSendType } from "../../api/TokenApi";
import Icon from "../../components/Icon";
import { registerCheckRequest, registerCodeRequest, registerSkipStep, resendSMSLoginCode, sms2Login } from "../../services/TokenService";
import { codeCooldown, isMobileClient, validatePhone } from "../../utils/CommonUtil";
import { getQuery } from "../../utils/UrlUtil";
import "./index.scss";

enum LoginType {
  QRCODE = 1,
  SMS = 2
}
const { Option } = Select;
interface LoginState {
  ifrUrl: string;
  loginType: LoginType;
  codeValue: string;
  mobileValue: string;
  validationBtnTxt: string;
  canGetCode: boolean;
  loading: boolean;
  currentMobileNotQtUser: boolean; // 当前sms登录手机号是否是轻推用户
}
export default class Login extends Component<{}, LoginState> {
  constructor(props: any) {
    super(props);
    this.state = {
      ifrUrl: "",
      loginType: LoginType.SMS,
      codeValue: '',
      mobileValue: '',
      validationBtnTxt: '获取验证码',
      loading: false,
      canGetCode:true,
      currentMobileNotQtUser: true,
    };
  }
  public componentDidMount() {
    const ifrQueryUrl = getQuery("qrcodeUrl");
    this.setState({
      ifrUrl: ifrQueryUrl || ""
    });
    window.addEventListener('message', (e: any) => {
      if(e.origin.indexOf('qingtui') !== -1 && typeof(e.data) === 'string' && e.data.indexOf('drive/preview') !== -1) {
        // 重定向到分享链接页面 
        window.location.href = e.data;
      } else {
        if(e.origin.indexOf('qingtui') !== -1 && typeof(e.data) === 'string' && e.data.indexOf('no-auth') !== -1) {
          // tslint:disable-next-line:no-commented-code
          // const fileId = e.data.split('fileId=')[1].replace('&redirect=yes', '');
          window.location.href = window.location.origin.replace('wps', 'web') + `/drive/preview/no-auth`;
        }
        else if(e.origin.indexOf('qingtui') !== -1 && typeof(e.data) === 'string' && e.data.indexOf('https://') !== -1) {
          console.log(e + '-------重定向信息--------');
          window.location.href = e.data.slice(0, e.data.indexOf('redirect=yes'));
        }
      }
    })
     const isMobile = isMobileClient();
     if(isMobile) {
      window.location.href = window.location.origin.replace('wps', 'web') + `/drive/preview/${getQuery('fileId') || ''}`;
     }
  }
  public codeCooldownCallback = (cooldownSeconds: number) => {
    if (cooldownSeconds > 0) {
      this.setState({
        validationBtnTxt: `${cooldownSeconds}秒后重新发送`,
        canGetCode: false
      })
    } else {
      this.setState({
        validationBtnTxt: `获取验证码`,
        canGetCode: true
      })
    }
  }

  public getCode = () => {
    const { mobileValue } = this.state;
    if(!validatePhone(mobileValue)) {
      message.warn('请输入正确的手机号');
      return;
    }
    resendSMSLoginCode({
      countryCode: '+86',
      mobilePhone: this.state.mobileValue,
      sendType: SMSSendType.SMS_LOGIN,
      verifyHeader: ''
    }).then((data: any) => {
      codeCooldown({
        timeTag: 'weboffive-timetag',
        cooldown: data.cooldown,
        callback: this.codeCooldownCallback
      })
    }).catch((e) => {
      if(String(e.code) === '46001') {
        // 用户不存在 直接走注册用户跳过 获取token 然后再短信登录
        registerCodeRequest({countryCode: '+86', mobilePhone: this.state.mobileValue,verifyHeader: ''}).then((data: any) => {
          // 1.获取注册验证码
          codeCooldown({
            timeTag: 'qt-registry-timetag',
            cooldown: data.cooldown,
            callback: this.codeCooldownCallback
          })
        }).then(() => {
          this.setState({
            currentMobileNotQtUser: false
          });
        }).catch(() => {
          message.error('获取验证码失败');
        })
      } else if(String(e.code) === '48007') {
        this.setState({
          loginType: LoginType.QRCODE
        });
        if(!this.state.ifrUrl) {
          this.getQrcodeUrl();
        }
        message.error('当前手机号验证码获取已达上限，请使用轻推扫码登录查看');
      }
       else {
        message.error('获取验证码失败');
      }
    })
  }

  public buildSmsButton = () => {
    const { canGetCode } = this.state
    return (
      <div className="getcode-btn">
        <span className={canGetCode ? "text" : "text-none"} onClick={canGetCode ? this.getCode : undefined}>{this.state.validationBtnTxt}</span>
      </div>
    )
  }

  public smsLogin = () => {
    const { codeValue, mobileValue, ifrUrl, currentMobileNotQtUser } = this.state;
    if(!validatePhone(mobileValue)) {
      message.warn('请输入正确的手机号');
      return;
    }
    if(codeValue && mobileValue) {
      this.setState({
        loading: true
      });
      if(currentMobileNotQtUser) {
        // 轻推用户直接短信登录
        sms2Login({
          countryCode: '+86',
          phone: mobileValue,
          authCode: codeValue,
          verifyHeader: ''
        }).then((data: any) => {
          this.setState({
            loading: false
          });
          const token = data.accessToken;
          const orgin = window.location.origin.replace('wps', 'web');
          if(!ifrUrl) {
            // 直接复制weboffice页面的url没有qrcodeurl
            const newUrl = orgin + `/drive/preview/${getQuery('fileId')}?accessToken=${token}`;
            window.location.href = newUrl; // 登录成功打开分享页面
          } else {
            const redirectUrl = decodeURIComponent(ifrUrl).split('redirect_uri=').pop() + "&accessToken=" + token;
            const temp = (redirectUrl as any).split('fileId=').pop().replace('&accessToken', '?accessToken');
            const newUrl = orgin + '/drive/preview/' + temp;
            window.location.href = newUrl; // 登录成功打开分享页面
          }
        }).catch((e) => {
          if(String(e.code) === '40001') {
            message.error('验证码错误');
          } else {
            message.error('系统繁忙，请稍后再试');
          }
          this.setState({
            loading: false
          });
        })
      } else {
        // 非轻推用户走默认注册流程
        // 验证验证码 成功则进行默认用户注册的跳过操作
        registerCheckRequest({countryCode: '+86', validateCode: this.state.codeValue, mobilePhone: this.state.mobileValue}).then(() => {
          // 注册用户
          // tslint:disable-next-line:no-identical-functions
          registerSkipStep('+86', this.state.mobileValue).then((data: any) => {
            this.setState({
              loading: false
            });
            // 拿到token直接打开分享页面
            const token = data.accessToken;
            const orgin = window.location.origin.replace('wps', 'web');
            const redirectUrl = decodeURIComponent(ifrUrl).split('redirect_uri=').pop() + "&accessToken=" + token;
            const temp = (redirectUrl as any).split('fileId=').pop().replace('&accessToken', '?accessToken');
            const newUrl = orgin + '/drive/preview/' + temp;
            window.location.href = newUrl; // 登录成功打开分享页面
          }).catch(() => {
            this.setState({
              loading: false
            });
            message.error('获取验证码失败');
          })
        }).catch((error: any) => {
          this.setState({
            loading: false
          });
          if(String(error.code) === '40001') {
            message.error('验证码错误');
          } else {
            message.error('系统繁忙，请稍后再试');
          }
        })
      }
    }
  }

  public getQrcodeUrl = () => {
    fetchQrcodeUrl(getQuery('fileId') || '').then((data: any) => {
      if(!data.shareOpen) {
        window.location.href = window.location.origin.replace('wps', 'web') + `/drive/preview/no-auth`;
      } else if(data.scanUrl) {
        const tempUrl = data.scanUrl.split('?')[1];
        this.setState({
          ifrUrl: tempUrl ? decodeURIComponent(tempUrl.slice("qrcodeurl=".length)) : '',
        });
      }
    }).catch(() => {
      //
    })
  }

  // tslint:disable-next-line:cognitive-complexity
  public render() {
    const isMobile = isMobileClient();
    const { loginType } = this.state;
    if (!isMobile) {
      return (
        <div className="login-page-index">
          <div className="login-content">
            <div className="login-box">
              <div className="left">
                <img src={require("../../static/images/pic.svg")} />
              </div>
              <div className="login-form">
              <div className="switch-header">
                    <div className="white-cover"></div>
                    <Tooltip title={loginType === LoginType.SMS ? "二维码登录查看" : "手机号验证"}>
                    <div className="switch-form" onClick={() => {
                        this.setState({
                          loginType: this.state.loginType === LoginType.SMS ? LoginType.QRCODE : LoginType.SMS
                        });
                        if(this.state.loginType === LoginType.SMS && !this.state.ifrUrl) {
                          this.getQrcodeUrl();
                        }
                      }}>
                      <Icon className={this.state.loginType === LoginType.SMS ? "sms-icon" : "qrcode-icon"} value={this.state.loginType === LoginType.SMS ? "qt-icon-cloud_qrcode" : "qt-icon-cloud_phone_verify"} />
                      <img className="mark-shadow" src={require("./shadow.png")} />
                    </div>
                    </Tooltip>
                  </div>
                {loginType === LoginType.SMS ? <div className="sms-form">
                  <div className="tips">
                    该文档需要进行身份信息验证才能访问
                  </div>
                  <Input.Group compact>
                    <Select defaultValue="+86">
                      <Option value="+86">+86</Option>
                    </Select>
                    <Input value={this.state.mobileValue} onChange={(e) => {
                      this.setState({
                        mobileValue: e.target.value
                      })
                    }} style={{ width: '50%', marginBottom: '20px' }} placeholder="请输入手机号"/>
                  </Input.Group>
                  <Input value={this.state.codeValue} onChange={(e) => {
                    this.setState({
                      codeValue: e.target.value
                    });
                  }} className="code-input" placeholder="输入验证码" suffix={this.buildSmsButton()}  />
                  <div>
                    <Button loading={this.state.loading} onClick={this.smsLogin} disabled={!this.state.codeValue} type="primary" className={!this.state.codeValue ? "disable-btn" :"check-btn"}>查看文档</Button>
                  </div>
                </div> : <div className="qr-code-form">
                  <iframe
                    id="login-iframe"
                    src={this.state.ifrUrl}
                    className="code-form"
                    sandbox="allow-forms allow-scripts allow-same-origin allow-popups"
                  />
                  <div className="local-tips">
                    请用<span>「轻推」</span>手机端扫码登录后查看
                  </div>
                </div>}
              </div>
            </div>
          </div>
        </div>
      );
    }
    return null;
    // (
    //   <div className="mobile-tips-page">
    //     <img src={require("../../static/images/pic.svg")} />
    //     <div className="tips">
    //       请用<span className="highlight">「轻推」</span>打开此链接查看文件
    //     </div>
    //   </div>
    // );
  }
}



// WEBPACK FOOTER //
// ./src/features/Login/index.tsx