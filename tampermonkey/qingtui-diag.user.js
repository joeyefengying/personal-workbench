// ==UserScript==
// @name         轻推登录诊断 (Qingtui Login Diag)
// @namespace    https://github.com/joeyefengying/personal-workbench
// @version      0.1.0
// @description  记录扫码登录全过程的 Cookie/URL/请求/Storage 变化
// @author       浩哥
// @match        *://wps.qingtui.com/*
// @match        *://web.qingtui.com/*
// @match        *://open.qingtui.com/*
// @grant        GM_getValue
// @grant        GM_setValue
// @run-at       document-start
// @license      MIT
// ==/UserScript==

(function () {
    'use strict';

    var LOG_KEY = '__qt_diag_log';
    var MAX_LOGS = 500;

    function log(msg, data) {
        var entry = {
            t: new Date().toISOString().substr(11, 12),
            url: location.href.substr(0, 120),
            msg: msg
        };
        if (data) entry.data = data;
        var logs = GM_getValue(LOG_KEY, []);
        logs.push(entry);
        if (logs.length > MAX_LOGS) logs = logs.slice(-MAX_LOGS);
        GM_setValue(LOG_KEY, logs);
        console.log('[QT Diag]', entry.t, msg, data || '');
    }

    function snapshotCookies() {
        var pairs = document.cookie.split(';');
        var cookies = {};
        for (var i = 0; i < pairs.length; i++) {
            var pair = pairs[i].trim();
            var idx = pair.indexOf('=');
            if (idx > 0) {
                var name = pair.substring(0, idx);
                var val = pair.substring(idx + 1);
                // 只记前30字符 + 长度
                cookies[name] = val.substr(0, 30) + '...(len=' + val.length + ')';
            }
        }
        return cookies;
    }

    function snapshotStorage() {
        var items = {};
        try {
            for (var i = 0; i < localStorage.length; i++) {
                var key = localStorage.key(i);
                var val = localStorage.getItem(key);
                items[key] = (val || '').substr(0, 30) + '...(len=' + (val || '').length + ')';
            }
        } catch (e) {}
        return items;
    }

    // ============ 1. 初始状态 ============
    log('=== 脚本启动 ===', {
        host: location.hostname,
        hash: location.hash,
        cookies: snapshotCookies(),
        storage: snapshotStorage()
    });

    // ============ 2. 监听 Cookie 变化 ============
    var lastCookies = JSON.stringify(snapshotCookies());
    setInterval(function () {
        var now = JSON.stringify(snapshotCookies());
        if (now !== lastCookies) {
            var oldKeys = Object.keys(JSON.parse(lastCookies));
            var newKeys = Object.keys(JSON.parse(now));
            var added = newKeys.filter(function (k) { return oldKeys.indexOf(k) < 0; });
            var removed = oldKeys.filter(function (k) { return newKeys.indexOf(k) < 0; });
            log('Cookie 变化', { added: added, removed: removed, current: snapshotCookies() });
            lastCookies = now;
        }
    }, 500);

    // ============ 3. 监听 localStorage 变化 ============
    var lastStorage = JSON.stringify(snapshotStorage());
    setInterval(function () {
        var now = JSON.stringify(snapshotStorage());
        if (now !== lastStorage) {
            log('Storage 变化', { current: snapshotStorage() });
            lastStorage = now;
        }
    }, 500);

    // ============ 4. 监听 URL/hash 变化 ============
    var lastUrl = location.href;
    setInterval(function () {
        if (location.href !== lastUrl) {
            log('URL 变化', { from: lastUrl.substr(0, 120), to: location.href.substr(0, 120) });
            lastUrl = location.href;
        }
    }, 300);

    // ============ 5. 拦截 fetch 请求 ============
    var origFetch = window.fetch;
    window.fetch = function () {
        var url = arguments[0];
        if (typeof url === 'string') {
            log('fetch → ' + url.substr(0, 150));
        } else if (url && url.url) {
            log('fetch → ' + url.url.substr(0, 150));
        }
        return origFetch.apply(this, arguments).then(function (resp) {
            if (typeof url === 'string' || (url && url.url)) {
                var u = typeof url === 'string' ? url : url.url;
                log('fetch ← ' + resp.status + ' ' + u.substr(0, 80), {
                    status: resp.status,
                    headers: {
                        'set-cookie': resp.headers.get('set-cookie') ? 'present' : 'none',
                        'location': resp.headers.get('location') || '',
                        'content-type': resp.headers.get('content-type') || ''
                    }
                });
            }
            return resp;
        });
    };

    // ============ 6. 拦截 XMLHttpRequest ============
    var origOpen = XMLHttpRequest.prototype.open;
    var origSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open = function (method, url) {
        this.__qtMethod = method;
        this.__qtUrl = url;
        return origOpen.apply(this, arguments);
    };
    XMLHttpRequest.prototype.send = function () {
        var self = this;
        log('XHR → ' + this.__qtMethod + ' ' + (this.__qtUrl || '').substr(0, 150));
        this.addEventListener('load', function () {
            log('XHR ← ' + self.status + ' ' + (self.__qtUrl || '').substr(0, 80), {
                status: self.status,
                responseHeaders: self.getAllResponseHeaders().split('\n').filter(function (h) {
                    return /set-cookie|location|content-type/i.test(h);
                })
            });
        });
        return origSend.apply(this, arguments);
    };

    // ============ 7. DOMContentLoaded ============
    document.addEventListener('DOMContentLoaded', function () {
        log('DOMContentLoaded', {
            hash: location.hash,
            title: document.title,
            cookies: snapshotCookies(),
            storage: snapshotStorage()
        });
    });

    // ============ 8. 页面卸载前记录 ============
    window.addEventListener('beforeunload', function () {
        log('beforeunload', { cookies: snapshotCookies() });
    });

    // ============ 9. 监听 postMessage (SSO 流程) ============
    window.addEventListener('message', function (event) {
        if (event.data && (event.data.action === 'sso' || event.data.accessToken || event.data.ssoData)) {
            log('postMessage 收到', {
                origin: event.origin,
                action: event.data.action,
                hasAccessToken: !!event.data.accessToken,
                hasSsoData: !!event.data.ssoData,
                dataKeys: Object.keys(event.data)
            });
        }
    });

    // ============ 10. 添加导出日志按钮 ============
    document.addEventListener('DOMContentLoaded', function () {
        setTimeout(function () {
            var btn = document.createElement('button');
            btn.textContent = '📋 导出诊断日志';
            btn.setAttribute('style',
                'position:fixed;bottom:10px;right:10px;z-index:99999;' +
                'padding:8px 14px;background:#1677ff;color:#fff;border:none;' +
                'border-radius:6px;cursor:pointer;font-size:13px;font-family:sans-serif;');
            btn.addEventListener('click', function () {
                var logs = GM_getValue(LOG_KEY, []);
                var text = logs.map(function (e) {
                    return e.t + ' | ' + e.msg + (e.data ? ' | ' + JSON.stringify(e.data) : '');
                }).join('\n');
                var blob = new Blob([text], { type: 'text/plain' });
                var a = document.createElement('a');
                a.href = URL.createObjectURL(blob);
                a.download = 'qt-diag-' + Date.now() + '.txt';
                a.click();
            });
            document.body.appendChild(btn);

            // 也显示日志条数
            var info = document.createElement('div');
            info.setAttribute('style',
                'position:fixed;bottom:40px;right:10px;z-index:99999;' +
                'padding:4px 8px;background:rgba(0,0,0,0.7);color:#0f0;' +
                'border-radius:4px;font-size:11px;font-family:monospace;');
            info.textContent = 'QT Diag: ' + GM_getValue(LOG_KEY, []).length + ' logs';
            document.body.appendChild(info);
        }, 2000);
    });

    log('诊断脚本已挂载, 等待用户操作...');
})();
