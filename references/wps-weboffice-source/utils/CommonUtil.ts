import { isNumber } from 'lodash';
export function isMobileClient() {
  if (navigator.userAgent.match(/(iPhone|iPod|Android|ios|iPad)/i)) {
    return true;
  }
  return false;
}


/*
倒计时
timeTag=缓存每次倒计时到本地的标记名
cooldown=倒计时时长，单位=s；如果不传，会从本地获取上次存在timeTag的cooldown倒计时
callback=每计时1s会执行一次，返回当前剩余倒计时；如果没有倒计时，默认返回0；
*/
export function codeCooldown(options: {
  timeTag: string;
  cooldown?: number;
  callback(a: number): void;
}) {
  let { cooldown } = options;
  const { timeTag, callback } = options;
  const oldCooldownTag = `${timeTag}-cooldown`;
  const codeOldTimeTag = `${timeTag}-time`;
  if (!cooldown && !isNumber(cooldown)) {
    const oldCooldown = Number(
      window.localStorage.getItem(oldCooldownTag) || 0
    ); // 单位-s
    const codeOldTime = Number(
      window.localStorage.getItem(codeOldTimeTag) || 0
    ); // 时间戳
    if (codeOldTime && oldCooldown) {
      const nowTime = new Date().getTime();
      cooldown = numToFixed(oldCooldown - (nowTime - codeOldTime) / 1000);
      if (cooldown > 0) {
        codeCooldown({ timeTag, cooldown, callback });
      } else {
        callback(0);
      }
    } else {
      callback(0);
    }
  } else {
    callback(cooldown);
    if (cooldown < 1) {
      return;
    }
    window.localStorage.setItem(oldCooldownTag, cooldown + '');
    window.localStorage.setItem(
      codeOldTimeTag,
      new Date().getTime().toString()
    );
    setTimeout(() => {
      codeCooldown({
        timeTag,
        callback,
        cooldown: --(cooldown as number)
      });
    }, 1000);
  }
}

export function numToFixed(temp: number, length?: number): number {
  // length=需要保留的小数点位数，默认0
  const tempIndex = Number(temp || 0);
  const tempLength = Number(length || 0) || 0;
  if (!Number.isNaN(tempIndex) && !Number.isNaN(tempLength)) {
    return Number((tempIndex / 1).toFixed(tempLength));
  } else {
    return 0;
  }
}

export function validatePhone(phone: string) {
  let regExp: any;
  regExp = new RegExp('^(1[3,4,5,6,7,8,9])\\d{9}$');
  if (regExp) {
    return regExp.test(phone);
  }
  return true;
}


// WEBPACK FOOTER //
// ./src/utils/CommonUtil.ts