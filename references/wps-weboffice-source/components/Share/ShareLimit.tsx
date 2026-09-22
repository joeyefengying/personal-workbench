import React, {Component} from "react";

import {message, Radio, Tooltip} from "antd";

import {getWeboffice, setShare} from "../../api/ShareApi";
import {getQuery} from "../../utils/UrlUtil";


interface Props {
    shareOpens: any
    initData: any
    setShareOpen: any
}

interface State {
    isWebOffice: boolean,
    fileType: boolean,
}

class ShareLimit extends Component<Props, State> {
    constructor(props: any) {
        super(props);
        this.state = {
            isWebOffice: false,
            fileType: getQuery('fileType') ==='rtf',
        }
    }

    public componentDidMount() {
        getWeboffice().then((res) => {
            this.setState({
                isWebOffice: res.data.webofficeEnable
            })
        })
    }

    public shareOnChange = (e: any) => {
        const data = this.props.initData({permission: e.target.value})
        setShare(data).then(() => {
            this.props.setShareOpen()
        }).catch(() => {
            message.error('请求失败,请检查网络')
        })
    }

    public render() {
        return (
            <div className={'card-box'}>
                <div className={'card-left'}>分享权限 :</div>
                <Radio.Group onChange={this.shareOnChange}
                             value={this.props.shareOpens && this.props.shareOpens.permission ? this.props.shareOpens.permission : 1}>
                    <Radio value={1}>仅预览</Radio>
                    <Radio value={3}>可下载</Radio>
                    <Tooltip placement="top" title={this.state.isWebOffice && !this.state.fileType ? null : '此格式暂不支持编辑状态'}>
                        <Radio value={5} disabled={!(this.state.isWebOffice && !this.state.fileType)}>可编辑</Radio>
                    </Tooltip>
                </Radio.Group>
            </div>
        );
    }
}

export default ShareLimit


// WEBPACK FOOTER //
// ./src/components/Share/ShareLimit.tsx