import { Canceler } from 'axios';
import ClientVersionBO from '../models/bo/ClientVersionBO';
import { transformClientVersion } from '../transformers/ClientVersionTransformer';
import * as RequestUtil from '../utils/RequestUtil';
import ClientVersionForm from './models/ClientVersionModel';

/**
 * 获取客户端版本
 *
 * @export
 * @param {ClientVersionForm} clientVersionForm
 * @returns {Promise<ClientVersionBO>}
 */
export function fetchClientVersion(clientVersionForm: ClientVersionForm): Promise<ClientVersionBO> {
  return RequestUtil.sendRequest({
    url: '/team/clientupdate',
    method: RequestUtil.Method.GET,
    data: clientVersionForm,
    cancelExecutor(canceler: Canceler) {
      // 调用canceler取消请求
    },
  }).then(data => {
    const versionData = data.update && data.update.webVersions ? data.update.webVersions[0] : {};
    return transformClientVersion(versionData);
  });
}



// WEBPACK FOOTER //
// ./src/api/ClientVersionApi.ts