import { TokenBO } from '../models/bo/TokenBO';
import * as RequestUtil from '../utils/RequestUtil';

export const REFRESH_TOKEN_URL = 'api/drive/token/refresh'; // 刷新token


export function fetchQrcodeUrl(fileId: string) {
  return RequestUtil.sendRequest({
    url: `drive/share/open/file/detail`,
    method: RequestUtil.Method.GET,
    data: {
      shareOpenId: fileId
    }
  }).then((res) => {
    return res.data || {};
  });
}

export function refreshAccessToken(refreshToken: string, headers?: any): Promise<TokenBO> {
  return RequestUtil.sendRequest({
    headers,
    url: REFRESH_TOKEN_URL,
    method: RequestUtil.Method.GET,
    data: {
      refreshToken,
    },
  }).then((refreshTokenResponse: any) => {
      return refreshTokenResponse.data || {};
  });
}

export function ackRefreshToken(refreshToken: string): Promise<TokenBO> {
  return RequestUtil.sendRequest({
    url: 'api/drive/security/ack',
    method: RequestUtil.Method.GET,
    data: {
      refreshToken,
    },
  }).then((refreshTokenResponse: any) => {
    return refreshTokenResponse.data || {};
  });
}

// 短信发送类型
export enum SMSSendType {
  SMS_LOGIN = 1, // 短信登录
}
// 短信登录步骤
export enum SMSStepType {
  INPUT_PHONE = 'input_phone', // 输入手机号 第一步
  VALIDATE_CODE = 'validateCode', //  验证 验证吗 第二步
  RESEND_VALIDATE_CODE = 'resend_validate_code', // 重新发送验证码的时候，第三步，不一定会出现
}
// 短信发送实体类
export interface SMSSendModel {
  countryCode: string;
  mobilePhone: string;
  sendType: SMSSendType;
  verifyHeader: string;
  stepType?: SMSStepType;
}
/**
 * 发送短信验证码，6位数
 *
 * @export
 * @param {SMSSendModel} smsSendModel
 * @returns
 */
 export function resendSMSLoginAuthCode(smsSendModel: SMSSendModel) {
  let headers = {};
  if (smsSendModel.verifyHeader) {
    // 组装滑动验证码header
    headers = {
      Verification: smsSendModel.verifyHeader
    };
  }
  // tslint:disable-next-line:no-commented-code
  // (headers as any).CLIENT = 'QingTui/52400;Macintosh, Intel Mac OS X 10_15_7;Web;0';
  // (headers as any).signature = 'signature';
  return RequestUtil.sendRequest({
    headers,
    url: 'login/sms/send',
    method: RequestUtil.Method.POST,
    data: smsSendModel,
  }).then(response => {
    if (response) {
      return response.data;
    }
    return response;
  });
}

export interface LoginFormModel {
  countryCode?: string;
  phone?: string;
  authCode?: string;
  verifyHeader?: string;
}

/**
 * 短信验证登录
 *
 * @export
 * @param {LoginFormModel} loginForm
 * @returns
 */
 export function smsLogin(loginForm: LoginFormModel) {
  let headers = {};
  if (loginForm.verifyHeader) {
    // 组装滑动验证码header
    headers = {
      Verification: loginForm.verifyHeader,
    };
  }
  return RequestUtil.sendRequest({
    headers,
    url: 'login/sms/verification/code/drive',
    method: RequestUtil.Method.GET,
    data: {
      countryCode: loginForm.countryCode,
      mobilePhone: loginForm.phone,
      smsAuthCode: loginForm.authCode,
      deviceType: 'tms',
    },
  });
}

// 新用户跳过登录获取轻推token
export function registerSkip(countryCode: string, mobilePhone: string) {
  return RequestUtil.sendRequest({
    url: 'account/register/default',
    method: RequestUtil.Method.POST,
    data: { countryCode, mobilePhone },
  });
}

interface RegisterBaseModel {
  countryCode: string;
  mobilePhone: string;
}
// 注册实体类
export interface RegisterSendModel extends RegisterBaseModel {
  verifyHeader: string; // 滑动验证码
}

// 验证 验证码
export interface RegisterValidateModel extends RegisterBaseModel {
  validateCode: string;
  verifyHeader?: string; // 滑动验证码
}
/**
 * 发送注册请求
 * @param resetPasswordSendModel
 */
 export function sendRegisterCodeRequest(registerSendModel: RegisterSendModel) {
  return RequestUtil.sendRequest({
    url: 'account/register/code/send',
    method: RequestUtil.Method.POST,
    headers: {
      Verification: registerSendModel.verifyHeader,
    },
    data: {
      mobilePhone: registerSendModel.mobilePhone,
      countryCode: registerSendModel.countryCode,
      sso: false,
    },
  });
}

/**
 * 发送 验证验证码请求
 * @param registerValidateModel
 */
 export function sendRegisterCheckRequest(registerValidateModel: RegisterValidateModel) {
  return RequestUtil.sendRequest({
    url: 'account/register/code/check',
    method: RequestUtil.Method.GET,
    headers: {
      Verification: registerValidateModel.verifyHeader || '',
    },
    data: {
      mobilePhone: registerValidateModel.mobilePhone,
      countryCode: registerValidateModel.countryCode,
      smsCode: registerValidateModel.validateCode,
    },
  });
}


// WEBPACK FOOTER //
// ./src/api/TokenApi.ts