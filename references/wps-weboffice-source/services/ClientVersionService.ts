import * as ClientVersionApi from '../api/ClientVersionApi';
import ClientVersionForm from '../api/models/ClientVersionModel';
import ClientVersionBO from '../models/bo/ClientVersionBO';

/**
 * 获取客户端版本
 *
 * @export
 * @param {ClientVersionForm} clientVersionForm
 * @returns {Promise<ClientVersionBO>}
 */
export function fetchClientVersion(clientVersionForm: ClientVersionForm): Promise<ClientVersionBO> {
  return ClientVersionApi.fetchClientVersion(clientVersionForm);
}



// WEBPACK FOOTER //
// ./src/services/ClientVersionService.ts