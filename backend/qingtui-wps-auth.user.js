// ==UserScript==
// @name         轻推WPS文档Chrome直开
// @namespace    https://wps.qingtui.com
// @version      1.0
// @description  拦截WPS编辑器iframe的API请求，注入Authorization头，实现Chrome直接打开轻推文档
// @match        https://wps.qingtui.com/*
// @run-at       document-start
// @grant        none
// ==/UserScript==

(function() {
  'use strict';

  // 从 localStorage 或 URL 参数获取 token
  function getAccessToken() {
    // 1. 尝试从 URL 参数获取
    const params = new URLSearchParams(window.location.search);
    let token = params.get('webofficeAccessToken');
    if (token) return token;

    // 2. 尝试从 localStorage 获取 (按 fileId)
    const fileId = params.get('fileId');
    if (fileId) {
      token = localStorage.getItem(fileId + '-wbo_accessToken');
      if (token) return token;
    }

    // 3. 遍历 localStorage 找任意有效的 wbo_accessToken
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.endsWith('-wbo_accessToken')) {
        token = localStorage.getItem(key);
        if (token) return token;
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

  // 刷新 token
  async function refreshToken(oldToken, refreshTokenValue) {
    try {
      const resp = await fetch(
        'https://wps.qingtui.com/wps/api/drive/token/refresh?refreshToken=' + refreshTokenValue,
        {
          headers: { 'Authorization': 'Bearer ' + oldToken },
        }
      );
      const text = await resp.text();
      const atMatch = text.match(/<accessToken>([^<]+)<\/accessToken>/);
      const rtMatch = text.match(/<refreshToken>([^<]+)<\/refreshToken>/);
      if (atMatch && rtMatch) {
        // 更新 localStorage
        const params = new URLSearchParams(window.location.search);
        const fileId = params.get('fileId');
        if (fileId) {
          localStorage.setItem(fileId + '-wbo_accessToken', atMatch[1]);
          localStorage.setItem(fileId + '-wbo_refreshToken', rtMatch[1]);
        }
        return atMatch[1];
      }
    } catch (e) {
      console.warn('[QT-Auth] Token refresh failed:', e);
    }
    return null;
  }

  // 获取有效 token (必要时刷新)
  async function getValidToken() {
    let token = getAccessToken();
    if (!token) return null;
    if (!isTokenExpired(token)) return token;

    // Token 过期，尝试刷新
    const params = new URLSearchParams(window.location.search);
    const fileId = params.get('fileId');
    if (fileId) {
      const rt = localStorage.getItem(fileId + '-wbo_refreshToken');
      if (rt) {
        const newToken = await refreshToken(token, rt);
        if (newToken) return newToken;
      }
    }
    return token; // 返回过期 token (可能仍然部分可用)
  }

  // 同步获取 token (用于拦截, 不等待刷新)
  function getTokenSync() {
    return getAccessToken();
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
      const token = getTokenSync();
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
      const token = getTokenSync();
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

  console.log('[QT-Auth] WPS Authorization interceptor installed');
})();
