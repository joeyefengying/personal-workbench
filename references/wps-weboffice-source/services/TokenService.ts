import * as TokenApi from '../api/TokenApi';
// tslint:disable-next-line:no-duplicate-imports
import {
  LoginFormModel,
  RegisterSendModel,
  registerSkip,
  RegisterValidateModel,
  resendSMSLoginAuthCode,
  sendRegisterCheckRequest,
  sendRegisterCodeRequest,
  smsLogin,
  SMSSendModel,
} from '../api/TokenApi';
import { TokenBO } from '../models/bo/TokenBO';
// tslint:disable-next-line:no-commented-code
// import store from '../store/ConfigureStore';
import { getServerTimestamp } from '../utils/DateUtil';
import { decBase64, encBase64 } from '../utils/SecurityUtil';
import { getFileIdFromUrl } from '../utils/UrlUtil';

/**
 * 解析accessToken中的信息
 * @param accessToken
 * @returns {*} {type,expires,aid}
 */
export function parseAccessToken(accessToken: string) {
  const arr = accessToken.split('.');
  if (arr && arr.length && arr[1]) {
    return JSON.parse(decBase64(arr[1]));
  }
}

/**
 * 验证accessToken是否过期
 * @param accessToken
 */
export function isAccessTokenExpired(accessToken: string) {
  if (!accessToken) {
    return false;
  }
  const expires = parseAccessToken(accessToken).expireTime;
  // 过期时间剩余一定时间，便认为已过期
  console.log(expires + 'expireTime');
  console.log(getServerTimestamp() + 'getServerTimestamp');
  return expires - getServerTimestamp() < 2 * 60 * 1e3; // （剩余过期时间）
}

// tslint:disable-next-line:no-commented-code
// export function getCurrentAccountToken(): TokenBO {
//   return {
//     refreshToken: getCurrentAccountByKey('refreshToken'),
//     accessToken: getCurrentAccountByKey('accessToken'),
//   };
// }

/**
 * 更新token
 * @param tokenInfo
 */
// export function updateAccountToken(tokenInfo: TokenBO): Promise<TokenBO> {
//   const accountId: string = parseAccessToken(tokenInfo.accessToken).aid;
//   let updatePromise: Promise<any> = Promise.resolve();
// //   if (appConfig.remember) {
// //     // 只有"记住我"才更新token到db中
// //     updatePromise = AccountDao.updateAccountToken(accountId, tokenInfo);
// //   }
//   store.dispatch(updateAccountTokenAction(tokenInfo));
//   return updatePromise.then(() => {
//     return Promise.resolve(tokenInfo);
//   });
// }

// tslint:disable-next-line:no-commented-code
// export function getTokenString(teamId?: string): string {
//   let tokenString: string = '';
//   const account = getCurrentAccountAll();
//   if (account) {
//     tokenString = account.accessToken;
//     if (teamId) {
//       tokenString += `.${encBase64(teamId)}`;
//     }
//   }
//   return tokenString;
// }

function getCookie(name: string) {
  const arr: any = [];
  const reg = new RegExp('(^| )' + name + '=([^;]*)(;|$)');
  if (arr === document.cookie.match(reg)) {
    return unescape(arr[2]);
  }
  return null;
}

export function refreshAccessToken(refreshToken: string): Promise<TokenBO> {
  return (
    TokenApi.refreshAccessToken(refreshToken)
      .then(tokenInfo => {
        if (tokenInfo) {
          // tslint:disable-next-line:no-commented-code
          // return updateAccountToken(tokenInfo);
          // 更新本地存储的token
          setAccessToken(tokenInfo.accessToken, getFileIdFromUrl() || '');
          setRefreshToken(tokenInfo.refreshToken, getFileIdFromUrl() || '');
          const logData = {
            data: {
              accessToken: tokenInfo.accessToken,
              refreshToken: tokenInfo.refreshToken,
            },
            qt_weboffice_token: getCookie('qt_weboffice_token'),
          };
          console.log('qt_weboffice_token' + JSON.stringify(logData));
        }
        return tokenInfo;
      })
      .then(tokenInfo => {
        // 本地更新accessToken后再调用，否则accessToken获取本地是过期的
        if (tokenInfo) {
          TokenApi.ackRefreshToken(tokenInfo.refreshToken);
        }
        // 每次刷新token 都设置一下weboffice的token
        (window as any).WEBOFFICE_INSTANCE.setToken({
          token: tokenInfo.accessToken,
          timeout: 11 * 60 * 1000,
        });
        return tokenInfo;
      })
      // .then((tokenInfo) => {
      //   const doms: any = document.querySelector(".web-office-iframe");
      //   if(doms) {
      //     doms.src = doms.src.slice(0, doms.src.indexOf('webofficeAccessToken')) +  'webofficeAccessToken=' + tokenInfo.accessToken;
      //   }
      //   return tokenInfo;
      // })
      .catch(error => {
        // tslint:disable-next-line:no-console
        console.warn('refresh token error', error);
        return Promise.reject(error);
      })
  );
}

export function getAccessToken(fileId: string) {
  return window.localStorage.getItem(`${fileId}-wbo_accessToken`);
}

export function setAccessToken(token: string, fileId: string) {
  return window.localStorage.setItem(`${fileId}-wbo_accessToken`, token);
}

export function getRefreshToken(fileId: string) {
  return window.localStorage.getItem(`${fileId}-wbo_refreshToken`);
}

export function setRefreshToken(token: string, fileId: string) {
  return window.localStorage.setItem(`${fileId}-wbo_refreshToken`, token);
}

export function getAuthorizationHeader(param?: { teamId: string }): string {
  let authorization: string = '';
  const accessToken: string = getAccessToken(getFileIdFromUrl() || '')!;
  if (accessToken) {
    authorization = 'Bearer ';
    if (param && param.teamId) {
      // 参数中有teamId
      authorization += `${accessToken}.${encBase64(param.teamId)}`;
    } else {
      authorization += `${accessToken}`;
    }
    return authorization;
  }
  return '';
}

export function replaceTokenWhenRefresh() {
  const searchs = window.location.search.split('&');
  searchs[10] = 'webofficeAccessToken=' + getAccessToken(getFileIdFromUrl() || '');
  searchs[11] = 'webofficeRefreshToken=' + getRefreshToken(getFileIdFromUrl() || '');
  const tempSearch = searchs.join('&');
  window.location.href = window.location.origin + window.location.pathname + tempSearch;
}

export function parseTokenExpireTime(urlToken: string, localToken: string) {
  const urlExpireTime = parseAccessToken(urlToken).expireTime;
  const localExpireTime =
    localToken && localToken !== 'undefined' ? parseAccessToken(localToken).expireTime : 0;
  if (urlExpireTime > localExpireTime) {
    // 如果url上的token的过期时间大于本地token的过期时间
    return true;
  }
  return false;
}

/**
 * 发送短信登录验证码
 *
 * @export
 * @param {SMSSendModel} smsSendModel
 * @returns
 */
export function resendSMSLoginCode(smsSendModel: SMSSendModel) {
  return resendSMSLoginAuthCode(smsSendModel);
}

/**
 * 短信验证登录
 *
 * @export
 * @param {LoginFormModel} loginForm
 * @returns
 */
export function sms2Login(loginForm: LoginFormModel) {
  return smsLogin(loginForm).then(response => {
    if (response) {
      return response.data;
    }
    return response;
  });
}

// 注册跳过 拿到token
export function registerSkipStep(countryCode: string, mobilePhone: string) {
  return registerSkip(countryCode, mobilePhone).then((data: any) => {
    return data.data;
  });
}

/**
 * 发送注册请求
 * @param registerSendModel
 */
export function registerCodeRequest(registerSendModel: RegisterSendModel) {
  return sendRegisterCodeRequest(registerSendModel).then(data => {
    if (data) {
      return data.data;
    }
    return null;
  });
}

/**
 * 发送 验证验证码请求
 * @param registerValidateModel
 */
export function registerCheckRequest(registerValidateModel: RegisterValidateModel) {
  return sendRegisterCheckRequest(registerValidateModel);
}



// WEBPACK FOOTER //
// ./src/services/TokenService.ts