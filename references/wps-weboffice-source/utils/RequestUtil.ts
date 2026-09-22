/**
 * 请求封装工具类
 */

import axios, { AxiosRequestConfig, AxiosResponse, Canceler } from "axios";
import qs from "qs";
import webSecurity from "web-security";
import BizException from "../exceptions/BizException";
import { ErrorCode } from "../exceptions/ErrorCode";
import { getAuthorizationHeader } from "../services/TokenService";
import { uuid } from "../utils/UUID";
import history from '../store/History';
import {
  correctionServerTime,
  getClientHeader,
  getServerTimestamp
} from "./DateUtil";
import { parseBigJSON } from "./JSONParse";
const CancelToken = axios.CancelToken;
const appDomain = window.location.origin.replace("wps", "web");

export enum Method {
  GET = "get",
  POST = "post",
  PUT = "put"
}

interface RequestHeader {
  [key: string]: string | null;
}

/**
 * 请求参数
 */
export interface RequestParam {
  url: string;
  method: Method;
  data?: any;
  timeout?: number;
  retry?: number;
  headers?: RequestHeader;
  cancelExecutor?: (canceler: Canceler) => void;
  responseType?: string; // 表示服务器响应的数据类型，可以是 'arraybuffer', 'blob', 'document', 'json', 'text', 'stream'
}

interface CustomRequestConfig extends AxiosRequestConfig {
  url: string;
  requestId: string; // 每次请求的唯一标识ID
  requestFilterKey: string; // 用于过滤请求的key
  retry: number; // 请求重试次数
  oriParam: any; // 请求的原始数据
}

interface FilterUrl {
  url: string;
  keyGenerator: (config: CustomRequestConfig) => string;
}

// 需要过滤请求的url配置
// 通过keyGenerator生成请求标识，标识一致，则认为请求一致
const filterUrlConfig: { [url: string]: FilterUrl } = {
  "/team/clientupdate": {
    url: "/team/clientupdate",
    keyGenerator(config: CustomRequestConfig) {
      return `${config.url}_${config.oriParam.clientType}`;
    }
  }
};

function getRequestKey(config: CustomRequestConfig): string {
  const item = filterUrlConfig[config.url];
  if (item) {
    return item.keyGenerator(config);
  }
  return config.requestId;
}

// 正在pending的请求
const pendingRequest = {};

function pushPendingRequest(config: CustomRequestConfig, data: any) {
  const key = config.requestFilterKey;
  if (pendingRequest[key]) {
    pendingRequest[key].push(data);
  } else {
    pendingRequest[key] = [];
    pendingRequest[key].push(data);
  }
}

function isRequestPending(config: CustomRequestConfig): boolean {
  const requestList = pendingRequest[config.requestFilterKey] || [];
  return requestList.length > 1;
}

function execRequestResolve(requestFilterKey: string, data: any): void {
  const requestList = pendingRequest[requestFilterKey];
  for (const request of requestList) {
    request.resolve(data);
  }
  delete pendingRequest[requestFilterKey];
}

function execRequestReject(requestFilterKey: string, error: Error): void {
  const requestList = pendingRequest[requestFilterKey];
  for (const request of requestList) {
    request.reject(error);
  }
  delete pendingRequest[requestFilterKey];
}
function handleResponse(response: AxiosResponse) {
  const originalRequest = response.config as CustomRequestConfig;
  const data = response.data || {};
  correctionServerTime(response.headers.date); // 校正服务器时间x
  // 其他响应接口
  if (data.code && data.code !== 0 && data.code !== 200) {
    if(originalRequest.url
        && originalRequest.url.includes("document/permission/edit")
        && data.message && data.message.includes("5610001")) {
      return history.replace('/qrcode-login');
    }
    console.warn(
      "[request failed]",
      "url",
      originalRequest.url,
      // 'teamId',
      // originalRequest.teamId,
      data.code,
      data.message
    );

    return Promise.reject(
      new BizException(`[${data.code}]${data.message || ""}`, data.data)
    );
  }

  // 正常响应接口
  return Promise.resolve(data);
}

// 参数序列化
axios.defaults.paramsSerializer = params => {
  return qs.stringify(params, { indices: false });
};

// 添加响应拦截器
axios.interceptors.response.use(
  response => {
    const data = response.data || {};
    correctionServerTime(response.headers.date); // 校正服务器时间
    if (data.ok === false) {
      // 旧版接口：ok===false
      return Promise.reject(new BizException(data.error));
    }
    if (data.code && data.code !== 0 && data.code !== 200) {
      // 新版接口：有code，且code值不为0和200，请求返回失败
      return Promise.reject(
        new BizException(`[${data.code}]${data.message || ""}`)
      );
    }
    // 正常响应接口
    return Promise.resolve(data);
  },
  error => {
    const resp = error.response;
    if (resp && resp.data && resp.data.code) {
      return handleResponse(resp);
    }
    let errorMsg = ErrorCode.REQUEST_FAILED;
    if (resp) {
      const status = resp.status;
      if (status === 404) {
        errorMsg = ErrorCode.NOT_FOUND;
      }
    } else if (error.code === "ECONNABORTED") {
      // 超时
      errorMsg = ErrorCode.TIME_OUT;
    }
    // 请求出错，如网络连接不通
    // 超时，404等，直接抛回异常
    return Promise.reject(new BizException(errorMsg));
  }
);

/**
 *
 * @param {RequestParam} param
 * @param param.teamId
 * @param param.timeout default: 20000
 */
// tslint:disable-next-line:cognitive-complexity
export function sendRequest(param: RequestParam) {
  return new Promise<any>((resolve, reject) => {
    const headers: any = {
      ...param.headers
      // 'Content-Type': param.method === Method.PUT ? 'application/x-www-form-urlencoded' : undefined
    };
    headers.Authorization = headers.Authorization
      ? headers.Authorization
      : getAuthorizationHeader() || null;
    let baseUrl = "";
    if (
      param.url.indexOf("login/sms/send") >= 0 ||
      param.url.indexOf("verification/code") >= 0 ||
      param.url.indexOf("register/default") >= 0 ||
      param.url.indexOf("register/code/send") >= 0 ||
      param.url.indexOf("register/code/check") >= 0
    ) {
      baseUrl = appDomain + "/api";
      headers.Authorization = null;
      headers.CLIENT = getClientHeader();
      headers.Signature = webSecurity.signUrl(
        "",
        param.data,
        getServerTimestamp(),
        getClientHeader()
      );
    }
    if (param.url.indexOf("open/file/detail") >= 0) {
      baseUrl = appDomain + "/api";
      headers.Authorization = null;
    }
    const config: CustomRequestConfig = {
      headers,
      baseURL: baseUrl,
      url: param.url,
      method: param.method,
      cancelToken: new CancelToken(canceler => {
        if (typeof param.cancelExecutor === "function") {
          param.cancelExecutor(canceler);
        }
      }),
      oriParam: param.data,
      requestId: uuid(),
      requestFilterKey: "",
      withCredentials: true,
      retry: typeof param.retry === "number" ? param.retry : 2,
      timeout: typeof param.timeout === "number" ? param.timeout : 20000,
      transformResponse: (data: any) => {
        if (typeof data === "string") {
          try {
            return parseBigJSON(data);
          } catch (e) {
            console.error("transformResponse", e);
            return data;
          }
        }
        return data;
      }
    };
    if (config.method === Method.POST) {
      config.data = qs.stringify(param.data, { indices: false });
    } else {
      config.params = param.data;
    }

    config.requestFilterKey = getRequestKey(config);
    // 存入pending列表中
    pushPendingRequest(config, {
      resolve,
      reject,
      requestId: config.requestId
    });
    if (!isRequestPending(config)) {
      // 没有正在发送的请求
      // 发送该请求，请求成功回调会在response的拦截器中执行
      axios(config)
        .then(response => {
          execRequestResolve(config.requestFilterKey, response);
        })
        .catch(error => {
          execRequestReject(config.requestFilterKey, error);
        });
    }
  });
}



// WEBPACK FOOTER //
// ./src/utils/RequestUtil.ts