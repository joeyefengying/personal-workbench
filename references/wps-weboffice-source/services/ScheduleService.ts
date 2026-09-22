import { getFileIdFromUrl } from "../utils/UrlUtil";
import { getAccessToken, getRefreshToken, isAccessTokenExpired, refreshAccessToken } from "./TokenService";

let refreshTokenTimer: any = null;

// 获取accessToken刷新时间（ms）
const GET_ACCESS_TOKEN_INTERVAL = 11 * 60 * 1000;


/**
 * 当app上线时需要启动的定时任务
 */
 export function startScheduleWhenOnline() {
    startPollUpdateRefreshToken();
  }

  // 轮询刷新token
function startPollUpdateRefreshToken() {
    if (refreshTokenTimer === null) {
      refreshTokenTimer = window.setInterval(() => {
        const accessToken = getAccessToken(getFileIdFromUrl() || '');
        const refreshToken = getRefreshToken(getFileIdFromUrl() || '');
        if (
            accessToken && refreshToken && isAccessTokenExpired(accessToken)
        ) {
          // token过期，需要刷新token
          refreshAccessToken(refreshToken);
        }
      }, GET_ACCESS_TOKEN_INTERVAL);
    }
  }

  function stopPollUpdateRefreshToken() {
    window.clearInterval(refreshTokenTimer);
    refreshTokenTimer = null;
  }


/**
 * 当app离线时需要停止的定时任务
 */
export function stopScheduleWhenOffline() {
    stopPollUpdateRefreshToken();
  }


// WEBPACK FOOTER //
// ./src/services/ScheduleService.ts