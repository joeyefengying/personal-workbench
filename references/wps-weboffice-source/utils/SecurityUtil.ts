import CryptoJS from 'crypto-js';
/**
 * 根据盐值md5加密密码
 *
 * @export
 * @param {string} password
 * @returns {string}
 */
 export function encryptMD5Password(password: string): string {
    return CryptoJS.MD5(`${password}{7zs1JKiilF}`).toString();
  }
  
  export function encryptMD5(content: string): string {
    return CryptoJS.MD5(`${content}`).toString();
  }
  
  export function encBase64(str: string): string {
    try {
      if (str) {
        const wordArray = CryptoJS.enc.Utf8.parse(str);
        return CryptoJS.enc.Base64.stringify(wordArray);
      } else {
        return '';
      }
    } catch (e) {
      console.error('encBase64', str, e);
      return '';
    }
  }
  
  export function decBase64(encodedStr: string): string {
    try {
      if (encodedStr) {
        return CryptoJS.enc.Base64.parse(encodedStr).toString(CryptoJS.enc.Utf8);
      } else {
        return '';
      }
    } catch (e) {
        console.error('decBase64', encodedStr, e);
      return '';
    }
  }


// WEBPACK FOOTER //
// ./src/utils/SecurityUtil.ts