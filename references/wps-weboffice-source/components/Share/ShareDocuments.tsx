import React, {Component} from "react";

import {message, Switch, Tooltip} from "antd";
import {getQuery} from "../../utils/UrlUtil";

import {setShareOpens} from "../../api/ShareApi";


interface Props {
    shareOpens: any;
    setShareOpen: any
}

class ShareDocuments extends Component<Props> {
    constructor(props: any) {
        super(props);
    }

    public changeSwitch = () => {
        try {
            const resourceId = getQuery('fileId') as string;
            const operation = this.props.shareOpens.shareOpen ? 2 : 1
            setShareOpens(operation, resourceId, 1).then((res) => {
                this.props.setShareOpen()
            }).catch(() => {
                message.error('请求失败,请检查网络')
            })
        } catch (err) {
            message.error('请求失败,请检查网络')
        }
    }

    public render() {
        return (
            <div className={'card-share-box'}>
                <div className={'card-left'}>分享文档 :</div>
                <Tooltip
                    placement="topLeft"
                    title={this.props.shareOpens && this.props.shareOpens.shareOpen
                        ? '关闭后所有分享者将无法查看此文档'
                        : null}
                >
                    <Switch onChange={this.changeSwitch}
                            checked={this.props.shareOpens && this.props.shareOpens.shareOpen ? this.props.shareOpens.shareOpen : false}
                    />
                </Tooltip>
            </div>
        )
    }
}

export default ShareDocuments


// WEBPACK FOOTER //
// ./src/components/Share/ShareDocuments.tsx