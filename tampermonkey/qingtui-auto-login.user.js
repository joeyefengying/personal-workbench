// ==UserScript==
// @name         轻推文档自动登录 v14 (Qingtui Auto Login)
// @namespace    https://github.com/joeyefengying/personal-workbench
// @version      14.0.0
// @description  缓存accessToken, 拦截XHR/fetch注入Authorization头, 让API直接返回webofficeUrl
// @author       浩哥
// @match        *://web.qingtui.com/*
// @match        *://wps.qingtui.com/*
// @match        *://wps2.qingtui.com/*
// @grant        GM_getValue
// @grant        GM_setValue
// @run-at       document-start
// @license      MIT
// ==/UserScript==

(function () {
    'use strict';

    function log(msg, data) {
        console.log('[QT v14]', msg, data || '');
        var logs = GM_getValue('__qt_v14_log', []);
        logs.push({ t: new Date().toISOString().substr(11, 12), msg: msg, data: data });
        if (logs.length > 300) logs = logs.slice(-300);
        GM_setValue('__qt_v14_log', logs);
    }

    function getParam(name, url) {
        var m = new RegExp('[?&]' + name + '=([^&]*)').exec(url || '');
        return m ? decodeURIComponent(m[1]) : null;
    }

    // ============================================================
    // web.qingtui.com — 缓存 accessToken + 拦截请求注入 Authorization
    // ============================================================

    if (location.hostname === 'web.qingtui.com') {
        log('=== v14 启动 (web.qingtui.com) ===', { url: location.href.substr(0, 150) });

        // 缓存 accessToken
        var urlToken = getParam('accessToken', location.href);
        if (urlToken) {
            log('✅ URL 含 accessToken, 缓存', { token: urlToken.substr(0, 30) + '...' });
            GM_setValue('__qt_access_token', urlToken);
            GM_setValue('__qt_token_time', Date.now());
        }

        var cachedToken = GM_getValue('__qt_access_token', '');
        var tokenAge = Date.now() - GM_getValue('__qt_token_time', 0);
        var tokenValid = cachedToken && tokenAge < 24 * 60 * 60 * 1000;
        if (tokenValid) {
            log('✅ 有效缓存 token', { age: Math.round(tokenAge / 1000) + 's' });
        }

        // ── 拦截 XHR: 注入 Authorization 头 ──
        var origOpen = XMLHttpRequest.prototype.open;
        var origSend = XMLHttpRequest.prototype.send;
        var origSetHeader = XMLHttpRequest.prototype.setRequestHeader;

        XMLHttpRequest.prototype.open = function (method, url) {
            this.__qtUrl = url;
            this.__qtMethod = method;
            return origOpen.apply(this, arguments);
        };

        XMLHttpRequest.prototype.send = function () {
            var self = this;

            // 注入 Authorization 头 (对 /api/ 开头的请求)
            if (tokenValid && this.__qtUrl && this.__qtUrl.indexOf('/api/') >= 0) {
                try {
                    origSetHeader.call(this, 'Authorization', 'Bearer ' + cachedToken);
                    log('🔑 注入 Authorization 头', { url: this.__qtUrl.substr(0, 80) });
                } catch (e) {
                    log('⚠️ 注入头失败', { error: String(e) });
                }
            }

            // 监听 /api/drive/ 响应
            if (this.__qtUrl && this.__qtUrl.indexOf('/api/drive/') >= 0) {
                this.addEventListener('load', function () {
                    log('XHR 响应', {
                        status: self.status,
                        url: self.__qtUrl.substr(0, 80),
                        body: self.responseText.substr(0, 200)
                    });
                });
            }

            return origSend.apply(this, arguments);
        };

        // ── 拦截 fetch: 注入 Authorization 头 ──
        var origFetch = window.fetch;
        if (origFetch) {
            window.fetch = function (input, init) {
                var url = typeof input === 'string' ? input : (input && input.url ? input.url : '');

                if (tokenValid && url.indexOf('/api/') >= 0) {
                    init = init || {};
                    init.headers = init.headers || {};
                    // 兼容 Headers 对象和普通对象
                    if (init.headers instanceof Headers) {
                        if (!init.headers.has('Authorization')) {
                            init.headers.set('Authorization', 'Bearer ' + cachedToken);
                            log('🔑 fetch 注入 Authorization', { url: url.substr(0, 80) });
                        }
                    } else {
                        if (!init.headers['Authorization']) {
                            init.headers['Authorization'] = 'Bearer ' + cachedToken;
                            log('🔑 fetch 注入 Authorization', { url: url.substr(0, 80) });
                        }
                    }
                }

                return origFetch.call(this, input, init).then(function (resp) {
                    if (url.indexOf('/api/drive/') >= 0) {
                        log('fetch 响应', { status: resp.status, url: url.substr(0, 80) });
                    }
                    return resp;
                });
            };
        }

        // ── 降级: 如果注入头后 API 仍返回 qrcodeUrl, 用重试 ──
        // (保留 v13 的重定向逻辑作为兜底, 但加了 30 秒冷却)
        var lastQrcodeRedirect = 0;

        XMLHttpRequest.prototype.send = (function (originalSend) {
            return function () {
                var self = this;
                if (this.__qtUrl && this.__qtUrl.indexOf('/api/drive/file/teamwork/open') >= 0) {
                    this.addEventListener('load', function () {
                        try {
                            var json = JSON.parse(self.responseText);
                            if (!json.data || !json.data.url) return;
                            var dataUrl = json.data.url;

                            if (dataUrl.indexOf('qrcodeUrl=') >= 0 && tokenValid) {
                                var now = Date.now();
                                if (now - lastQrcodeRedirect < 30000) {
                                    log('❌ qrcodeUrl 降级重试冷却中, 跳过', { age: now - lastQrcodeRedirect });
                                    return;
                                }
                                lastQrcodeRedirect = now;
                                var fileId = json.data.resourceId || getParam('fileId', self.__qtUrl);
                                log('⚠️ 注入头后仍返回 qrcodeUrl, 尝试重定向补 token', { fileId: fileId });
                                // 不再简单重定向 — 尝试直接 fetch 带 Authorization
                                fetch('/api/drive/file/teamwork/open?resourceId=' + fileId, {
                                    headers: { 'Authorization': 'Bearer ' + cachedToken }
                                }).then(function (r) { return r.json(); }).then(function (d) {
                                    if (d.data && d.data.url && d.data.url.indexOf('webofficeUrl=') >= 0) {
                                        log('✅ 带 Authorization 的请求成功, 跳转 webofficeUrl');
                                        location.href = d.data.url;
                                    } else {
                                        log('❌ 带 Authorization 仍失败, 可能 token 过期需扫码');
                                    }
                                }).catch(function (e) {
                                    log('❌ 降级 fetch 失败', { error: String(e) });
                                });
                            }
                        } catch (e) {}
                    });
                }
                return originalSend.apply(this, arguments);
            };
        })(XMLHttpRequest.prototype.send);

    }

    // ============================================================
    // wps.qingtui.com / wps2.qingtui.com — 仅记录, 不干预
    // ============================================================

    if (location.hostname === 'wps.qingtui.com' || location.hostname === 'wps2.qingtui.com') {
        log('=== v14 启动 (wps) ===', { host: location.hostname, url: location.href.substr(0, 120) });
    }

    // ============================================================
    // 导出日志按钮
    // ============================================================

    document.addEventListener('DOMContentLoaded', function () {
        setTimeout(function () {
            var btn = document.createElement('button');
            btn.textContent = '📋 导出v14日志';
            btn.setAttribute('style',
                'position:fixed;bottom:10px;right:10px;z-index:99999;' +
                'padding:8px 14px;background:#1677ff;color:#fff;border:none;' +
                'border-radius:6px;cursor:pointer;font-size:13px;font-family:sans-serif;');
            btn.addEventListener('click', function () {
                var logs = GM_getValue('__qt_v14_log', []);
                var text = logs.map(function (e) {
                    return e.t + ' | ' + e.msg + (e.data ? ' | ' + JSON.stringify(e.data) : '');
                }).join('\n');
                var blob = new Blob([text], { type: 'text/plain' });
                var a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = 'qt-v14-log-' + Date.now() + '.txt';
                a.click();
            });
            document.body.appendChild(btn);
        }, 2000);
    });

})();
