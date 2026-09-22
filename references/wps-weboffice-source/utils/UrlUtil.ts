// tslint:disable-next-line:no-commented-code
export function getUrlParams(search: string): Map<string, string> {
    let searchTemp = search;
    try {
      if (searchTemp.indexOf('?') < 0) {
        return new Map();
      }
      if (!searchTemp.startsWith('?')) {
        searchTemp = searchTemp.substr(searchTemp.indexOf('?'));
      }
      const paramsArray = searchTemp.substr(1).split('&');
      let key;
      let value;
      const result: Map<string, string> = new Map();
      for (const item of paramsArray) {
        const result2 = item.split('=');
        key = result2[0];
        value = decodeURIComponent(result2[1]);
        result.set(key, value);
      }
      return result;
    } catch (error) {
      console.log('获取url参数失败', error);
      return new Map();
    }
  }

// tslint:disable-next-line:no-commented-code
  export function getQuery(name: string) {
    const reg = new RegExp('(^|&)' + name + '=([^&]*)(&|$)');
    const r = window.location.search.substr(1).match(reg);
    if (r != null) {
      return decodeURIComponent(r[2]);
    }
    return null;
  }

// tslint:disable-next-line:no-commented-code
  export function getUrlLast(url: string) {
    const paramsArray = url.split('/');
    return paramsArray.pop();
  }

  export function getFileIdFromUrl() {
    return getQuery('fileId');
  }


  export function replaceLocationHash() {
    const requestPermission = getQuery('requestPermission') || '';
    const businessCode = getQuery('businessCode') || '';
    const fileId = getQuery('fileId');
    const fileType = getQuery('fileType');
    const webofficeUrl = getQuery('webofficeUrl');
    if(webofficeUrl) {
      setWebOfficeUrl(webofficeUrl, fileId!);
    }
    history.replaceState({}, '', `?requestPermission=${requestPermission}&businessCode=${businessCode}&fileId=${fileId}&fileType=${fileType}`);
  }

  export function setWebOfficeUrl(url: string, fileId: string) {
    window.localStorage.setItem(`${fileId}-webofficeUrl`, url);
  }

  export function getWebOfficeUrl(fileId: string) {
    return window.localStorage.getItem(`${fileId}-webofficeUrl`);
 }


// WEBPACK FOOTER //
// ./src/utils/UrlUtil.ts