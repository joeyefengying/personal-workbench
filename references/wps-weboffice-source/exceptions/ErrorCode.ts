/**
 * 错误码
 */
export enum ErrorCode {
  // 自定义错误码，以大写C开头的三位数字
  REQUEST_FAILED = 'C001', // 默认错误码，所有没有配置的错误码，均显示该错误信息
  TIME_OUT = 'C002',
  NOT_FOUND = '404',
  // 后端对应错误码
  SYSTEM_BUSY = '-1',
}

const errorCodeMessage = {};

// 客户端自定义错误码
errorCodeMessage[ErrorCode.REQUEST_FAILED] = 'error.request_failed';
errorCodeMessage[ErrorCode.TIME_OUT] = 'error.request_failed';
errorCodeMessage[ErrorCode.NOT_FOUND] = 'error.not_found';

// 后端对应错误码
errorCodeMessage[ErrorCode.SYSTEM_BUSY] = 'error.system_busy';

export { errorCodeMessage };



// WEBPACK FOOTER //
// ./src/exceptions/ErrorCode.ts