import React, {Component} from "react";

import {message, Radio} from "antd";
import {setShare} from "../../api/ShareApi";


interface Props {
    shareOpens: any
    initData: any
    setShareOpen: any
}

class ValidityDate extends Component<Props> {
    constructor(props: any) {
        super(props);
        this.state = {}
    }

    public validityOnChange = (e: any) => {
        const data = this.props.initData({expireType: e.target.value})
        setShare(data).then(() => {
            this.props.setShareOpen()
        }).catch(() => {
            message.error('请求失败,请检查网络')
        })
    }

    public render() {
        return (
            <div className={'card-box'}>
                <div className={'card-left'}>有效期 :</div>
                <Radio.Group onChange={this.validityOnChange}
                             value={this.props.shareOpens.expireType ? this.props.shareOpens.expireType : 1}>
                    <Radio value={4}>永久有效</Radio>
                    <Radio value={1}>24小时</Radio>
                    <Radio value={2}>7天</Radio>
                    <Radio value={3}>1个月</Radio>
                </Radio.Group>
            </div>
        )
    }
}

export default ValidityDate


// WEBPACK FOOTER //
// ./src/components/Share/ValidityDate.tsx