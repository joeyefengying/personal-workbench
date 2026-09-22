import { message, Tooltip } from 'antd';
import React, { Component } from 'react';

import { fetchEditPermission, fetchEditUrl } from '../../api/fileApi';
import { refreshAccessToken } from '../../api/TokenApi';
import Icon from '../../components/Icon';
import { startScheduleWhenOnline } from '../../services/ScheduleService';
import * as TokenService from '../../services/TokenService';

import history from '../../store/History';
import {
  getFileIdFromUrl,
  getQuery,
  getWebOfficeUrl,
  replaceLocationHash,
} from '../../utils/UrlUtil';
import './index.scss';
import WebOfficeSDK from './open-jssdk-v0.0.3.es';

import Share from '../../components/Share';

import { getPrivateDownloadUrl, getShareOpen, webOfficePermission } from '../../api/ShareApi';
import { getDate } from '../../utils/DateUtil';

import { isMobileClient } from '../../utils/CommonUtil';
import { TokenBO } from '../../models/bo/TokenBO';

enum CurrentMode {
  READ = 'read',
  WRITE = 'write',
}

interface HomeState {
  hasEditPermission: boolean;
  requestPermission: CurrentMode;
  intoHis: string;
  isShow: boolean;
  shareOpens: any;
  permission: boolean;
  url: string;
  resourceSpaceType: boolean;
  model: boolean;
  gmtExpire: any;
  download: boolean;
  share: boolean;
  shareSwitch: boolean;
  isQinTui: boolean;
}

export default class Home extends Component<{}, HomeState> {
  public webofficeContainer: any;
  public homeRef: any;
  public body: any;
  public fileName: string = '';

  constructor(props: any) {
    super(props);
    this.homeRef = React.createRef();
    this.state = {
      hasEditPermission: false,
      requestPermission: CurrentMode.READ,
      intoHis: '',
      shareOpens: {},
      permission: false,
      resourceSpaceType: false,

      isShow: false, // 分享框控制展示
      url: '', // 文件分享链接地址
      model: false, // 是否是web端
      gmtExpire: '', // 文件到期时间
      download: false, // 是否拥有下载权限
      share: false, // 是否拥有分享权限
      shareSwitch: false, // 是否拥有分享开关权限
      isQinTui: false, // 是否轻推文件
    };
  }

  public mountWindow = async (instance: any) => {
    await instance.ready();
    (window as any)._WPS_INSTANCE_ = instance;
    if (document.hidden !== undefined) {
      document.addEventListener('visibilitychange', () => {
        console.log('当前tab visible.hidden：', document.hidden);
        if (document.hidden) {
          // 如果当前页面为hidden true 重新设置下token
          console.log(
            '回到了当前tab的token：',
            TokenService.getAccessToken(getFileIdFromUrl() || '')
          );
          console.log(
            '当前token是否过期',
            TokenService.isAccessTokenExpired(
              TokenService.getAccessToken(getFileIdFromUrl() || '') || ''
            )
          );
          const accessToken = TokenService.getAccessToken(getFileIdFromUrl() || '');
          const refreshToken = TokenService.getRefreshToken(getFileIdFromUrl() || '');
          if (accessToken && refreshToken && TokenService.isAccessTokenExpired(accessToken)) {
            // token过期，需要刷新token
            TokenService.refreshAccessToken(refreshToken);
          }
          // (window as any)._WPS_INSTANCE_.setToken({
          //   token: TokenService.getAccessToken(getFileIdFromUrl() || ''),
          //   timeout: 8 * 60 * 1000,
          //   // hasRefreshTokenConfig: true
          // })
        }
      });
      document.addEventListener('focus', () => {
        console.log('当前tab focus：');
        this.handRefreshToken();
      });
      this.webofficeContainer.on("error", (data: any) => {
        // tslint:disable-next-line:no-console
        console.log(data);
      });

      this.webofficeContainer.on("fileStatus", (data: any) => {
        // tslint:disable-next-line:no-console
        console.log(data);
      });

    }
  };

  public handRefreshToken = () => {
    const accessToken = TokenService.getAccessToken(getFileIdFromUrl() || '');
    const refreshToken = TokenService.getRefreshToken(getFileIdFromUrl() || '');
    if (accessToken && refreshToken && TokenService.isAccessTokenExpired(accessToken)) {
      // token过期，需要刷新token
      TokenService.refreshAccessToken(refreshToken);
    }
  };

  public getTokenBO = async (): Promise<TokenBO> => {
    try {
      const fileId = getFileIdFromUrl() || '';

      let accessToken =
        getQuery('webofficeAccessToken') || TokenService.getAccessToken(fileId) || '';

      let refreshToken =
        getQuery('webofficeRefreshToken') || TokenService.getRefreshToken(fileId) || '';

      if (TokenService.isAccessTokenExpired(accessToken)) {
        ({ accessToken, refreshToken } = await TokenService.refreshAccessToken(refreshToken));
      }

      TokenService.setAccessToken(accessToken, fileId);
      TokenService.setRefreshToken(refreshToken, fileId);

      return { accessToken, refreshToken };
    } catch (error) {
      return {
        accessToken: '',
        refreshToken: '',
      };
    }
  };

  // tslint:disable
  public async componentDidMount() {
    const redirect = getQuery('redirect');
    if (redirect) {
      return history.replace('/middle-redirect');
    }

    const { accessToken } = await this.getTokenBO();
    if (!accessToken) {
      return history.replace('/qrcode-login');
    }

    const webofficeUrl = getQuery('webofficeUrl')
      ? getQuery('webofficeUrl')!
      : getWebOfficeUrl(getFileIdFromUrl() || '')!;
    const realUrl = atob(decodeURIComponent(webofficeUrl));
    const fileNameReg = /_w_third_fileName=(.*)&_w_third_fileType/;
    fileNameReg.exec(realUrl);
    this.fileName = decodeURIComponent(RegExp.$1 || '').replace(/\+/g, ' ');
    this.webofficeContainer = WebOfficeSDK.config({
      mount: document.querySelector('.home-page'),
      url: realUrl + '&_w_tokentype=1',
      // url: webofficeUrl + '&_w_tokentype=1',

      // onHyperLinkOpen: ({linkUrl}: any) => {
      //   console.log('进入拦截外链跳转函数' + linkUrl);
      //   if(linkUrl) {
      //     const prefix = window.location.origin + window.location.pathname;
      //     const newTabUrl = prefix + '?webofficeUrl=' + encodeURIComponent(linkUrl) + '&webofficeAccessToken=' + getAccessToken() + '&webofficeRefreshToken=' + getRefreshToken() + '&fileId=' + getQuery('fileId') + '&requestPermission=read' + '&intoHis=yes';
      //     window.location.href = newTabUrl;
      //   }
      // },
      // refreshToken: this.refreshTokenEvent // 设置刷新token
    });

    rebindOpen();
    [0, 500, 1000, 2000].forEach(ms => setTimeout(rebindOpen, ms));

    (window as any).WEBOFFICE_INSTANCE = this.webofficeContainer;
    this.mountWindow(this.webofficeContainer);

    // 设置token
    this.webofficeContainer.setToken({
      token: accessToken,
      timeout: 11 * 60 * 1000,
      // hasRefreshTokenConfig: true
    });
    // 保存token后开始定时刷token
    startScheduleWhenOnline();
    this.checkPermission();
    document.title = this.fileName || '轻推云文档';
    this.updateShareOpens();
    replaceLocationHash();
  }

  public refreshTokenEvent = async () => {
    const tokenInfo = await refreshAccessToken(
      TokenService.getRefreshToken(getFileIdFromUrl() || '') || ''
    );
    return {
      token: tokenInfo.accessToken,
      timeout: 11 * 60 * 1000,
    };
  };

  public checkPermission = async () => {
    try {
      const fileId = getQuery('fileId');
      const businessCode = getQuery('businessCode') || '';
      const requestPermission = getQuery('requestPermission') || '';
      const fileType = getQuery('fileType') || '';
      const his = getQuery('intoHis') || '';
      if (fileId) {
        const permission = await fetchEditPermission(fileId, businessCode, fileType);
        this.setState({
          hasEditPermission: permission,
          requestPermission: requestPermission.toLocaleLowerCase() as CurrentMode,
          intoHis: his,
        });
      }
    } catch (e) {
      this.setState({
        hasEditPermission: false,
      });
    }
  };
  public editFile = async () => {
    console.log(this.state.model);
    // 切换成编辑模式
    const fileName = decodeURIComponent(this.fileName || '');
    const fileId = getQuery('fileId');
    const fileType = getQuery('fileType');
    const bCode = getQuery('businessCode');
    try {
      const editUrl = await fetchEditUrl(fileId!, fileName, fileType!, bCode!);
      window.location.href = editUrl;
    } catch {
      message.error('获取编辑路径失败，请联系管理员');
    }
  };

  // 更新shareOpens
  public updateShareOpens = async () => {
    const businessCode = getQuery('businessCode') || '';
    const getModel = isMobileClient();
    const resourceId = getQuery('fileId') as string;
    if (businessCode === 'weboffice.qt') {
      this.setState({
        shareOpens: false,
        download: false,
        share: false,
        model: getModel,
        isQinTui: false,
      });
    } else {
      try {
        const share: any = await getShareOpen(resourceId, 1);
        const permission: any = await webOfficePermission(resourceId);
        this.setState({
          model: getModel,
          shareOpens: share.data,
          gmtExpire: getDate(share.data.gmtExpire),
          url: permission.data.previewUrl,
          share:
            share.data.shareOpen ||
            permission.data.sharePermission == 5 ||
            permission.data.sharePermission == 6,
          download:
            permission.data.downloadPermission == 3 ||
            permission.data.downloadPermission == 4 ||
            permission.data.downloadPermission == 5 ||
            permission.data.downloadPermission == 6,
          shareSwitch: permission.data.sharePermission == 5 || permission.data.sharePermission == 6,
          isQinTui: true,
        });
      } catch (e) {
        this.setState({
          shareOpens: false,
          download: false,
          share: false,
          model: getModel,
          isQinTui: false,
        });
      }
    }
  };

  // 下载文件
  public download = async () => {
    if (this.state.shareOpens && this.state.download) {
      const fileId = getQuery('fileId') as string;
      const fileName = this.fileName || '';
      try {
        // const res = await webOfficeLoad(fileId);
        let url = '';
        // if(res.data.storageType === DriveStorageType.PUBLIC) {
        //   const ossClient = new OSS({
        //     accessKeyId: res.data.publicSignature.accessKeyId,
        //     accessKeySecret: res.data.publicSignature.accessKeySecret,
        //     stsToken: res.data.publicSignature.securityToken,
        //     bucket: res.data.publicSignature.bucket,
        //     endpoint: res.data.publicSignature.endpoint,
        //     region: res.data.publicSignature.region,
        //   });
        //    url = ossClient.signatureUrl(res.data.publicSignature.key, {
        //     response: {
        //       'content-disposition': `attachment; filename*=UTF-8''${encodeURIComponent(
        //         fileName
        //       )}`,
        //     },
        //   });
        // } else {
        try {
          //  await getPrivateDownloadSignature({fileId, teamId: ''});
          url = await getPrivateDownloadUrl({ fileId, teamId: '' });
        } catch {
          message.error('获取下载Url失败');
        }
        // }
        const downloadLink = document.getElementById('download') as any;
        downloadLink.setAttribute('href', url);
        downloadLink.setAttribute('download', `${fileName}`);
        downloadLink.click();
      } catch {
        message.error('获取下载签名失败');
      }
    }
  };

  public setIsShow = () => {
    if (this.state.shareOpens && (this.state.share || this.state.shareOpens.shareOpen)) {
      this.setState({ isShow: !this.state.isShow });
    }
  };

  public render() {
    return (
      <div className="home-page" ref={this.homeRef}>
        {this.state.hasEditPermission &&
        this.state.requestPermission === CurrentMode.READ &&
        !this.state.intoHis ? (
          <div className="edit-btn" onClick={this.editFile}>
            <Icon value="qt-icon-edit" className="icon" />
            <span className="edit-btn-text">编辑</span>
          </div>
        ) : null}

        {!this.state.model && this.state.isQinTui ? (
          <>
            <Tooltip
              placement="left"
              title={this.state.shareOpens && this.state.share ? null : '无分享权限'}
            >
              <div
                className={this.state.shareOpens && this.state.share ? 'share' : 'noShare'}
                onClick={this.setIsShow}
              />
            </Tooltip>
            <Tooltip
              placement="left"
              title={this.state.shareOpens && this.state.download ? null : '无下载权限'}
            >
              <div
                className={this.state.shareOpens && this.state.download ? 'download' : 'noDownload'}
                onClick={this.download}
              />
            </Tooltip>
          </>
        ) : null}

        {this.state.isShow ? (
          <div
            style={{
              width: '100%',
              height: '100%',
              zIndex: 998,
              position: 'fixed',
            }}
            onClick={() => {
              this.setState({ isShow: false });
            }}
          />
        ) : null}

        {this.state.isShow ? (
          <Share
            shareOpens={this.state.shareOpens}
            updateShareOpens={this.updateShareOpens}
            permission={this.state.permission}
            url={this.state.url}
            gmtExpire={this.state.gmtExpire}
            shareSwitch={this.state.shareSwitch}
          />
        ) : null}
        <a id="download" />
      </div>
    );
  }
}

function rebindOpen() {
  const iframe = document.querySelector('#office-iframe');
  if (!(iframe instanceof HTMLIFrameElement)) {
    return;
  }
  const iframeWindow = iframe.contentWindow;
  if (!iframeWindow || iframeWindow === iframeWindow.parent) {
    return;
  }
  iframeWindow.open = iframeWindow.parent.open;
}



// WEBPACK FOOTER //
// ./src/features/Home/index.tsx