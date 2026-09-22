import _ from 'lodash';

// 本地时间减服务器的时间差(ms)
let localToServerTimeDiff = 0;

(Date.prototype as any).format = function(format: any) {
  const o = {
    'M+': this.getMonth() + 1,
    'd+': this.getDate(),
    'h+': this.getHours(),
    'm+': this.getMinutes(),
    's+': this.getSeconds(),
    'q+': Math.floor((this.getMonth() + 3) / 3),
    S: this.getMilliseconds(),
  };

  let result = format;
  if (/(y+)/.test(format)) {
    result = format.replace(RegExp.$1, (this.getFullYear() + '').substr(4 - RegExp.$1.length));
  }

  for (const k in o) {
    if (new RegExp('(' + k + ')').test(result)) {
      result = format.replace(
        RegExp.$1,
        RegExp.$1.length === 1 ? o[k] : ('00' + o[k]).substr(('' + o[k]).length)
      );
    }
  }

  return result;
};

/**
 * 校正服务器时间
 * (仅在底层Request调用)
 */
export function correctionServerTime(serverTimeStr: string) {
  const localTimeStamp = Date.now();
  const serverTimestamp = new Date(serverTimeStr).getTime();
  if (serverTimestamp > 0) {
    // 获取到的服务器时间是有一个有效值
    localToServerTimeDiff = localTimeStamp - serverTimestamp;
  }
}

/**
 * 获取服务器时间戳
 */
export function getServerTimestamp(): number {
  const localTimeStamp = Date.now();
  return localTimeStamp - localToServerTimeDiff;
}

/**
 * 获取服务器时间对象
 */
export function getServerDate(): Date {
  return new Date(getServerTimestamp());
}

/**
 * 根据时间戳获取日期对象，不传参数获取当前时间的日期对象
 *
 * @export
 * @param {(string | number | null | undefined)} stamp
 * @returns {Date}
 */
export function getDateFromTimestamp(stamp: string | number | null | undefined): Date {
  const timestamp = _.isNil(stamp) ? getServerTimestamp() : stamp;
  if (typeof timestamp === 'number') {
    return new Date(timestamp);
  }
  return new Date(parseInt(timestamp, 10));
}


export function getClientHeader(): string {
    const arr = [];
    const ua = navigator.userAgent;
    const result = ua.match(/([^\(\)]+)(?=\))/g);
    // 匹配userAgent中第一个小括号的内容,并替换掉其中的“;”
    const info = result && result.length > 0 ? result[0].replace(/;/g, ',') : 'Other';
  // 客户端版本
  arr.push('QingTui/' + '52300');
  // 操作系统
  arr.push(info);
  // 机器型号
    arr.push('Web');
  // appCode
  arr.push('0');
  return arr.join(';');
  // 'QingTui/3601;Macintosh, Intel Mac OS X 10_12_6;Web;0';
}

export function getDate(date:number){
  const time = new Date(date);
  const y = time.getFullYear();
  const m = time.getMonth()+1;
  const d = time.getDate();
  const h = time.getHours();
  const mm = time.getMinutes();
  return y+'/'+m+'/'+d+' '+h+':'+mm
}


// WEBPACK FOOTER //
// ./src/utils/DateUtil.ts