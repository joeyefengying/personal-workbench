import * as RequestUtil from '../utils/RequestUtil';


export const DRIVE_PREFIX = 'api/drive/';

export const SHARE_OPEN = DRIVE_PREFIX + 'resource/share/open/detail/v2';
export const SHARE_OPERATION = DRIVE_PREFIX + 'resource/share/open/operation/v2';
export const RESOURCE_SHARE_OPEN = DRIVE_PREFIX + 'resource/share/open';
export const SHARE_WEBOFFICE = DRIVE_PREFIX + 'resource/share/domain/weboffice/auth';
export const WEBOFFICE_DOWNLOAD = DRIVE_PREFIX + 'file/signature/download';
export const WEBOFFICE_PERMISSION=DRIVE_PREFIX +'file/team/space/permission';
export const FILE_DETAIL=DRIVE_PREFIX +'/share/open/file/detail';
export const DOWNLOAD_PRIVATE_URL = DRIVE_PREFIX +'file/signature/download';
export const DOWNLOAD_PRIVATE_SIGNATUE_URL = DRIVE_PREFIX +'file/signature/download/url';

export enum DriveStorageType {
    /** 公有云 */
    PUBLIC = 1,
    /** 私有云 */
    PRIVATE = 2,
  }
  
export interface PrivateSignature {
    bucket: string;
    contentType: string;
    expireTime: string;
    key: string;
    method: string;
    sign: string;
    url: string;
  }
  
  export interface PublicSignature {
    accessKeyId: string;
    accessKeySecret: string;
    baseUrl: string;
    bucket: string;
    endpoint: string;
    expiration: string;
    key: string;
    region: string;
    securityToken: string;
  }
  
  export interface DriveSignatureBO {
    storageType: DriveStorageType;
    privateSignature: PrivateSignature;
    publicSignature: PublicSignature;
  }
  

/**
 * 获取公开共享
 * @param resourceId    文件id/文件夹id
 * @param resourceType  1 文件；2 文件夹（当前版本均为1）
 */

export function getShareOpen(resourceId: string, resourceType: number) {
    return RequestUtil.sendRequest({
        url: SHARE_OPEN,
        method: RequestUtil.Method.GET,
        data: {
            resourceId,
            resourceType
        }
    })
}

/**
 * 开启/关闭公开共享
 * @param operation     1 开启，2 关闭，只关闭链接共享
 * @param resourceId    文件id/文件夹id
 * @param resourceType   1 文件；2 文件夹（当前版本均为1）
 */

export function setShareOpens(operation: number, resourceId: string, resourceType: number) {
    return RequestUtil.sendRequest({
        url: SHARE_OPERATION,
        method: RequestUtil.Method.PUT,
        data: {
            operation,
            resourceId,
            resourceType
        }
    })
}

/**
 * 设置公开共享
 * @param expireType  过期时间类型 1：24小时，2：7天，3：1个月，4：永久有效
 * @param permission  权限  1 查看；3 下载；5 编辑
 * @param resourceId   资源id   文件id/文件夹id
 * @param resourceType  资源类型  1 文件；2 文件夹（当前版本均为1）
 * @param scope         范围   1-获得链接的任何人，2-本企业内,3-指定人员
 */
interface Data {
    expireType: number
    permission: number
    resourceId: string
    resourceType: number
    scope: number
}

export function setShare(data: Data) {
    return RequestUtil.sendRequest({
        url: RESOURCE_SHARE_OPEN,
        method: RequestUtil.Method.PUT,
        data: {...data}
    })
}

/**
 * 获取编辑权限
 */
export function getWeboffice() {
    return RequestUtil.sendRequest({
        url: SHARE_WEBOFFICE,
        method: RequestUtil.Method.GET
    })
}

/**
 * 获取下载文件签名
 * @param fileId   文件id
 */
export function webOfficeLoad(fileId: string): Promise<{data: DriveSignatureBO}> {
    return RequestUtil.sendRequest({
        url: WEBOFFICE_DOWNLOAD,
        method: RequestUtil.Method.GET,
        data: {
            fileId
        }
    })
}

interface BaseParam {
    teamId: string;
}
export interface GetDownloadSignatureParam extends BaseParam {
    fileId: string;
}
/**
 * 获取私有云下载地址
 * @param param
 */
 export async function getPrivateDownloadSignature(param: GetDownloadSignatureParam): Promise<string> {
    const resp = await RequestUtil.sendRequest({
    //   teamId: param.teamId,
      url: DOWNLOAD_PRIVATE_URL,
      data: {
        fileId: param.fileId,
      },
      method: RequestUtil.Method.GET,
    });
  
    return resp.data;
}

export async function getPrivateDownloadUrl(param: GetDownloadSignatureParam): Promise<string> {
    const resp = await RequestUtil.sendRequest({
      url: DOWNLOAD_PRIVATE_SIGNATUE_URL,
      data: {
        fileId: param.fileId,
      },
      method: RequestUtil.Method.GET,
    });
  
    return resp.data;
  }
/**
 * 查看文件所在空间团队的权限
 * @param fileId
 */
export function  webOfficePermission(resourceId: string){
    return RequestUtil.sendRequest({
        url:WEBOFFICE_PERMISSION,
        method:RequestUtil.Method.GET,
        data:{
            resourceId
        }
    })
}

export function fileDetail (resourceId:string) {
    return RequestUtil.sendRequest({
        url:FILE_DETAIL,
        method:RequestUtil.Method.GET,
        data:{
            shareOpenId:resourceId
        }
    })
}




// WEBPACK FOOTER //
// ./src/api/ShareApi.ts