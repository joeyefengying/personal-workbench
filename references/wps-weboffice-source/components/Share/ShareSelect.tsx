import React, {Component} from "react";

import {message, Select} from "antd";
import {setShare} from "../../api/ShareApi";

interface Props {
    shareOpens: any;
    initData: any;
    setShareOpen: any;
}

class ShareSelect extends Component<Props> {
    constructor(props: any) {
        super(props);
    }

    public handleChange = (value: any) => {
        const data = this.props.initData({scope: value})
        setShare(data).then(() => {
            this.props.setShareOpen()
        }).catch(() => {
            message.error('请求失败,请检查网络')
        })
    }

    public render() {
        return (
            <div className={'card-box'}>
                <div className={'card-left'} style={{marginTop: '5px'}}>谁可以看 :</div>
                <Select
                    style={{width: 350}}
                    onChange={this.handleChange}
                    value={this.props.shareOpens.scope}
                >
                    <Select.Option value={2}>本企业内成员</Select.Option>
                    <Select.Option value={1}>获得链接的任何人</Select.Option>
                    <Select.Option value={3}>仅指定成员</Select.Option>
                </Select>
            </div>
        )
    }
}

export default ShareSelect


// WEBPACK FOOTER //
// ./src/components/Share/ShareSelect.tsx