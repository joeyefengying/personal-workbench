import { Canceler } from 'axios';
import * as RequestUtil from '../utils/RequestUtil';
/**
 * 检查是否有编辑权限
 *
 * @export
 * @param {fileId} fileId
 * @returns {Promise<true>}
 */
export async function fetchEditPermission(fileId: string, businessCode: string, fileType: string): Promise<boolean> {
  const data:any = await RequestUtil.sendRequest({
    url: 'api/drive/document/permission/edit',
    method: RequestUtil.Method.GET,
    data: {fileId, businessCode, fileType},
    cancelExecutor(canceler: Canceler) {
      // 调用canceler取消请求
    },
  });
  return data.data;
}

/**
 * 获取编辑URL
 *
 * @export
 * @param {fileId} fileId
 * @param {fileName} fileName
 * @param {fileType} fileType
 * @returns {Promise<true>}
 */
 export async function fetchEditUrl(fileId: string,fileName: string,fileType: string, businessCode: string): Promise<string> {
  const data:any = await RequestUtil.sendRequest({
    url: 'api/drive/document/url/edit',
    method: RequestUtil.Method.GET,
    data: {fileId, fileName, fileType, businessCode, requestPermission: 'write', },
    cancelExecutor(canceler: Canceler) {
      // 调用canceler取消请求
    },
  });
  return data.data.editUrl;
}



// WEBPACK FOOTER //
// ./src/api/fileApi.ts