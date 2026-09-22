// ==UserScript==
// @name         轻推WPS文档Chrome直开
// @namespace    https://wps.qingtui.com
// @version      1.2
// @description  拦截WPS编辑器iframe的API请求，注入Authorization头，实现Chrome直接打开轻推文档
// @match        https://wps.qingtui.com/*
// @run-at       document-start
// @all-frames   true
// @grant        none
// ==/UserScript==

(function() {
  'use strict';

  // 从 URL 参数或路径提取 fileId
  function getFileId() {
    const params = new URLSearchParams(window.location.search);
    let fileId = params.get('fileId');
    if (fileId) return fileId;
    // iframe URL: /weboffice/office/s/{fileId}
    const pathMatch = window.location.pathname.match(/\/s\/(\d{10,20})/);
    if (pathMatch) return pathMatch[1];
    // /drive/preview/{fileId}
    const pathMatch2 = window.location.pathname.match(/\/drive\/preview\/(\d{10,20})/);
    if (pathMatch2) return pathMatch2[1];
    return null;
  }

  // 从 localStorage 或 URL 参数获取 token
  function getAccessToken() {
    // 1. URL 参数 webofficeAccessToken (父页面)
    const params = new URLSearchParams(window.location.search);
    let token = params.get('webofficeAccessToken');
    if (token) return token;

    // 2. 按 fileId 从 localStorage 读
    const fileId = getFileId();
    if (fileId) {
      token = localStorage.getItem(fileId + '-wbo_accessToken');
      if (token) return token;
    }

    // 3. 遍历 localStorage 找任意 wbo_accessToken
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.endsWith('-wbo_accessToken')) {
        token = localStorage.getItem(key);
        if (token) return token;
      }
    }
    return null;
  }

  // 同步获取 refreshToken
  function getRefreshToken() {
    const params = new URLSearchParams(window.location.search);
    let rt = params.get('webofficeRefreshToken');
    if (rt) return rt;
    const fileId = getFileId();
    if (fileId) {
      rt = localStorage.getItem(fileId + '-wbo_refreshToken');
      if (rt) return rt;
    }
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.endsWith('-wbo_refreshToken')) {
        rt = localStorage.getItem(key);
        if (rt) return rt;
      }
    }
    return null;
  }

  // 检查 token 是否过期
  function isTokenExpired(token) {
    try {
      const parts = token.split('.');
      if (parts.length !== 3) return true;
      const payload = JSON.parse(atob(parts[1]));
      return Date.now() > payload.expireTime;
    } catch (e) {
      return true;
    }
  }

  // 异步刷新 token (不阻塞 XHR 拦截)
  let refreshing = false;
  let cachedToken = null;
  let cachedTokenTime = 0;

  async function refreshTokenIfNeeded() {
    if (refreshing) return;
    refreshing = true;
    try {
      let token = getAccessToken();
      if (!token || !isTokenExpired(token)) {
        refreshing = false;
        return;
      }
      const rt = getRefreshToken();
      if (!rt) {
        refreshing = false;
        return;
      }
      const resp = await fetch(
        'https://wps.qingtui.com/wps/api/drive/token/refresh?refreshToken=' + rt,
        { headers: { 'Authorization': 'Bearer ' + token } }
      );
      const text = await resp.text();
      const atMatch = text.match(/<accessToken>([^<]+)<\/accessToken>/);
      const rtMatch = text.match(/<refreshToken>([^<]+)<\/refreshToken>/);
      if (atMatch && rtMatch) {
        const fileId = getFileId();
        if (fileId) {
          localStorage.setItem(fileId + '-wbo_accessToken', atMatch[1]);
          localStorage.setItem(fileId + '-wbo_refreshToken', rtMatch[1]);
        }
        cachedToken = atMatch[1];
        cachedTokenTime = Date.now();
        console.log('[QT-Auth] Token refreshed');
      }
    } catch (e) {
      console.warn('[QT-Auth] Token refresh failed:', e);
    } finally {
      refreshing = false;
    }
  }

  // 获取有效 token (同步, 用于 XHR 拦截)
  function getValidTokenSync() {
    // 用缓存的刷新结果 (5分钟内)
    if (cachedToken && Date.now() - cachedTokenTime < 5 * 60 * 1000) {
      return cachedToken;
    }
    const token = getAccessToken();
    if (token) {
      // 如果过期, 异步刷新 (不阻塞当前请求, 下次请求会用新 token)
      if (isTokenExpired(token)) {
        refreshTokenIfNeeded();
      }
      return token; // 返回可能过期的 token, 总比没有好
    }
    return null;
  }

  // === 拦截 XMLHttpRequest ===
  const origXHROpen = XMLHttpRequest.prototype.open;
  const origXHRSend = XMLHttpRequest.prototype.send;
  const origXHRSetHeader = XMLHttpRequest.prototype.setRequestHeader;

  XMLHttpRequest.prototype.open = function(method, url) {
    this.__qt_url = url;
    this.__qt_headers = {};
    return origXHROpen.apply(this, arguments);
  };

  XMLHttpRequest.prototype.setRequestHeader = function(name, value) {
    this.__qt_headers[name] = value;
    return origXHRSetHeader.apply(this, arguments);
  };

  XMLHttpRequest.prototype.send = function(body) {
    const url = this.__qt_url || '';
    // 对 WPS API 调用注入 Authorization
    if (url.indexOf('/api/') >= 0 || url.indexOf('/v3/') >= 0) {
      const token = getValidTokenSync();
      if (token && !this.__qt_headers['Authorization']) {
        origXHRSetHeader.call(this, 'Authorization', 'Bearer ' + token);
      }
    }
    return origXHRSend.apply(this, arguments);
  };

  // === 拦截 fetch ===
  const origFetch = window.fetch;
  window.fetch = function(input, init) {
    init = init || {};
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    if (url.indexOf('/api/') >= 0 || url.indexOf('/v3/') >= 0) {
      const token = getValidTokenSync();
      if (token) {
        init.headers = init.headers || {};
        if (init.headers instanceof Headers) {
          if (!init.headers.has('Authorization')) {
            init.headers.set('Authorization', 'Bearer ' + token);
          }
        } else {
          if (!init.headers['Authorization']) {
            init.headers['Authorization'] = 'Bearer ' + token;
          }
        }
      }
    }
    return origFetch.call(this, input, init);
  };

  // 标记脚本已运行 (供前端检测)
  try {
    sessionStorage.setItem('qt_wps_auth_active', '1');
  } catch(e) {}

  console.log('[QT-Auth] WPS Authorization interceptor installed in', window.location.pathname);
})();
